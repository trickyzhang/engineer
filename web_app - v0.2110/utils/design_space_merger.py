"""
设计空间融合器 - 用于将导入的设计空间数据与Phase 1配置进行合并和同步
实现Phase 1 ↔ Phase 4的双向数据流
"""

import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from utils.state_manager import get_state_manager


class DesignSpaceMerger:
    """
    将导入的设计空间数据与Phase 1的设计变量和价值属性进行合并
    并实现双向同步
    """

    @staticmethod
    def merge_with_phase1(
        imported_data: Dict[str, Any],
        phase1_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        融合导入的设计空间数据与Phase 1配置

        参数:
        - imported_data: 来自DesignSpaceParser的解析结果
        - phase1_config: Phase 1的配置（如为None则从StateManager读取）

        返回: {
            'status': 'success'|'partial'|'error',
            'merged_variables': [...],
            'merged_attributes': [...],
            'new_variables': [...],
            'new_attributes': [...],
            'updates': {
                'phase1_variables': [...],
                'phase1_attributes': [...]
            },
            'conflicts': [...],
            'warnings': [...],
            'summary': str
        }
        """
        if phase1_config is None:
            # 从StateManager读取Phase 1配置
            state = get_state_manager()

            # 安全地加载数据，兼容DataFrame和list类型
            def _safe_load(phase, key):
                data = state.load(phase, key)
                if data is None:
                    return []
                if isinstance(data, pd.DataFrame):
                    return data.to_dict('records') if not data.empty else []
                if isinstance(data, list):
                    return data
                return []

            phase1_config = {
                'variables': _safe_load('phase1', 'design_variables'),
                'attributes': _safe_load('phase1', 'value_attributes'),
                'performance_metrics': _safe_load('phase1', 'performance_metrics')
            }

        result = {
            'status': 'success',
            'merged_variables': [],
            'merged_attributes': [],
            'new_variables': [],
            'new_attributes': [],
            'updates': {},
            'conflicts': [],
            'warnings': [],
            'summary': ''
        }

        # 检查导入数据有效性
        if 'error' in imported_data:
            result['status'] = 'error'
            result['summary'] = f"导入数据错误: {imported_data['error']}"
            return result

        imported_vars = imported_data.get('variables', [])
        imported_attrs = imported_data.get('attributes', [])
        phase1_vars = phase1_config.get('variables', [])
        phase1_attrs = phase1_config.get('attributes', [])

        # 1. 处理设计变量
        merged_vars, new_vars, var_conflicts = DesignSpaceMerger._merge_variables(
            imported_vars, phase1_vars
        )
        result['merged_variables'] = merged_vars
        result['new_variables'] = new_vars
        result['conflicts'].extend(var_conflicts)

        # 2. 处理价值属性/性能指标
        merged_attrs, new_attrs, attr_conflicts = DesignSpaceMerger._merge_attributes(
            imported_attrs, phase1_attrs
        )
        result['merged_attributes'] = merged_attrs
        result['new_attributes'] = new_attrs
        result['conflicts'].extend(attr_conflicts)

        # 3. 数据验证
        validation_warnings = DesignSpaceMerger._validate_merged_data(
            merged_vars, merged_attrs
        )
        result['warnings'].extend(validation_warnings)

        # 4. 生成Phase 1的更新数据
        result['updates']['phase1_variables'] = merged_vars
        result['updates']['phase1_attributes'] = merged_attrs

        # 5. 生成摘要
        result['summary'] = DesignSpaceMerger._generate_summary(
            new_vars, new_attrs, var_conflicts, attr_conflicts
        )

        if var_conflicts or attr_conflicts:
            result['status'] = 'partial'

        return result

    @staticmethod
    def _merge_variables(
        imported_vars: List[Dict],
        phase1_vars: List[Dict]
    ) -> Tuple[List[Dict], List[Dict], List[str]]:
        """
        合并设计变量

        返回: (merged_vars, new_vars, conflicts)
        """
        merged_vars = []
        new_vars = []
        conflicts = []

        # 构建Phase 1变量的查找表
        phase1_vars_by_name = {v.get('name', ''): v for v in phase1_vars}

        # 处理导入的变量
        for imp_var in imported_vars:
            var_name = imp_var.get('name', '')

            if var_name in phase1_vars_by_name:
                # 变量已存在，检查是否一致
                phase1_var = phase1_vars_by_name[var_name]
                merged_var = DesignSpaceMerger._merge_single_variable(
                    phase1_var, imp_var
                )

                # 检查冲突：只有当两个类型都定义且不同时才报告
                phase1_type = phase1_var.get('type')
                imported_type = imp_var.get('type')
                # 仅当两者都非None且不同时，才视为冲突
                if phase1_type is not None and imported_type is not None and phase1_type != imported_type:
                    conflicts.append(
                        f"变量'{var_name}'类型不一致: Phase1={phase1_type}, "
                        f"导入={imported_type}"
                    )

                merged_vars.append(merged_var)
            else:
                # 新变量
                new_vars.append(imp_var)
                merged_vars.append(imp_var)

        # 添加Phase 1中存在但导入数据中不存在的变量
        for var_name, phase1_var in phase1_vars_by_name.items():
            if not any(v.get('name') == var_name for v in imported_vars):
                merged_vars.append(phase1_var)

        return merged_vars, new_vars, conflicts

    @staticmethod
    def _merge_single_variable(phase1_var: Dict, imported_var: Dict) -> Dict:
        """
        合并单个设计变量定义

        优先级: 导入数据 > Phase 1（如果更完整）
        """
        merged = {**phase1_var}

        # 更新范围（如果导入数据更完整）
        if 'min' in imported_var and imported_var['min'] is not None:
            merged['min'] = imported_var['min']

        if 'max' in imported_var and imported_var['max'] is not None:
            merged['max'] = imported_var['max']

        # 保留Phase 1的描述信息
        if 'description' not in merged and 'description' in imported_var:
            merged['description'] = imported_var['description']

        # 更新单位
        if 'unit' in imported_var and imported_var['unit']:
            merged['unit'] = imported_var['unit']

        return merged

    @staticmethod
    def _merge_attributes(
        imported_attrs: List[Dict],
        phase1_attrs: List[Dict]
    ) -> Tuple[List[Dict], List[Dict], List[str]]:
        """
        合并价值属性/性能指标

        返回: (merged_attrs, new_attrs, conflicts)
        """
        merged_attrs = []
        new_attrs = []
        conflicts = []

        # 构建Phase 1属性的查找表
        phase1_attrs_by_name = {a.get('name', ''): a for a in phase1_attrs}

        # 处理导入的属性
        for imp_attr in imported_attrs:
            attr_name = imp_attr.get('name', '')

            if attr_name in phase1_attrs_by_name:
                # 属性已存在
                phase1_attr = phase1_attrs_by_name[attr_name]
                merged_attr = {**phase1_attr, **imp_attr}

                # 检查单位一致性
                if (phase1_attr.get('unit') and imp_attr.get('unit') and
                    phase1_attr.get('unit') != imp_attr.get('unit')):
                    conflicts.append(
                        f"属性'{attr_name}'单位不一致: Phase1={phase1_attr.get('unit')}, "
                        f"导入={imp_attr.get('unit')}"
                    )
                    # 保留Phase 1的单位（因为已配置）
                    merged_attr['unit'] = phase1_attr.get('unit')

                merged_attrs.append(merged_attr)
            else:
                # 新属性
                new_attrs.append(imp_attr)
                merged_attrs.append(imp_attr)

        # 添加Phase 1中存在但导入数据中不存在的属性
        for attr_name, phase1_attr in phase1_attrs_by_name.items():
            if not any(a.get('name') == attr_name for a in imported_attrs):
                merged_attrs.append(phase1_attr)

        return merged_attrs, new_attrs, conflicts

    @staticmethod
    def _validate_merged_data(
        merged_vars: List[Dict],
        merged_attrs: List[Dict]
    ) -> List[str]:
        """
        验证合并后的数据一致性

        返回: 警告消息列表
        """
        warnings = []

        # 检查变量
        for var in merged_vars:
            var_name = var.get('name', '')

            if var.get('type') == 'continuous':
                if 'min' not in var or 'max' not in var:
                    warnings.append(f"连续变量'{var_name}'缺少范围定义")
                elif var.get('min') >= var.get('max'):
                    warnings.append(f"连续变量'{var_name}'的min >= max")

        # 检查属性
        for attr in merged_attrs:
            attr_name = attr.get('name', '')
            if not attr.get('unit'):
                warnings.append(f"属性'{attr_name}'缺少单位定义")

        return warnings

    @staticmethod
    def _generate_summary(
        new_vars: List[Dict],
        new_attrs: List[Dict],
        var_conflicts: List[str],
        attr_conflicts: List[str]
    ) -> str:
        """
        生成融合摘要
        """
        summary = []

        if new_vars:
            summary.append(f"✅ 新增 {len(new_vars)} 个设计变量")
            for var in new_vars:
                summary.append(f"  - {var.get('name', 'Unknown')} ({var.get('type', 'unknown')})")

        if new_attrs:
            summary.append(f"✅ 新增 {len(new_attrs)} 个性能属性")
            for attr in new_attrs:
                summary.append(f"  - {attr.get('name', 'Unknown')} ({attr.get('unit', 'N/A')})")

        if var_conflicts:
            summary.append(f"⚠️ 设计变量冲突 ({len(var_conflicts)})")
            for conflict in var_conflicts:
                summary.append(f"  - {conflict}")

        if attr_conflicts:
            summary.append(f"⚠️ 性能属性冲突 ({len(attr_conflicts)})")
            for conflict in attr_conflicts:
                summary.append(f"  - {conflict}")

        if not summary:
            summary.append("✅ 数据已同步，无新增或冲突")

        return "\n".join(summary)

    @staticmethod
    def update_phase1_persistent(
        merged_data: Dict[str, Any],
        persist: bool = True
    ) -> Tuple[bool, str]:
        """
        将融合结果持久化到Phase 1配置

        参数:
        - merged_data: merge_with_phase1的返回结果
        - persist: 是否立即持久化到StateManager

        返回: (success, message)
        """
        if merged_data['status'] == 'error':
            return False, merged_data['summary']

        if not persist:
            return True, "融合完成，但未持久化"

        try:
            state = get_state_manager()

            # 保存更新的Phase 1配置
            updates = merged_data.get('updates', {})

            if 'phase1_variables' in updates:
                state.save('phase1', 'design_variables', updates['phase1_variables'])

            if 'phase1_attributes' in updates:
                state.save('phase1', 'value_attributes', updates['phase1_attributes'])

            # 记录融合元数据
            merge_info = {
                'timestamp': pd.Timestamp.now().isoformat(),
                'status': merged_data['status'],
                'new_variables': len(merged_data['new_variables']),
                'new_attributes': len(merged_data['new_attributes']),
                'conflicts': len(merged_data['conflicts']),
                'warnings': len(merged_data['warnings'])
            }
            state.save('phase4', 'last_merge_info', merge_info)

            message = f"Phase 1已更新: {merged_data['summary']}"
            return True, message

        except Exception as e:
            return False, f"持久化失败: {str(e)}"

    @staticmethod
    def get_reconciliation_report(
        merged_data: Dict[str, Any]
    ) -> str:
        """
        生成详细的数据对账报告
        """
        report = []

        report.append("=" * 60)
        report.append("📋 设计空间融合对账报告")
        report.append("=" * 60)

        # 基本信息
        report.append(f"\n状态: {merged_data['status'].upper()}")

        # 新增数据
        if merged_data['new_variables']:
            report.append(f"\n✨ 新增 {len(merged_data['new_variables'])} 个设计变量:")
            for var in merged_data['new_variables']:
                var_type = var.get('type', 'unknown')
                if var_type == 'continuous':
                    range_str = f"[{var.get('min', '?')} ~ {var.get('max', '?')}]"
                else:
                    range_str = f"{var.get('values', [])}"
                report.append(f"  • {var['name']}: {var_type} {range_str}")

        if merged_data['new_attributes']:
            report.append(f"\n✨ 新增 {len(merged_data['new_attributes'])} 个性能属性:")
            for attr in merged_data['new_attributes']:
                unit = attr.get('unit', 'N/A')
                report.append(f"  • {attr['name']} ({unit})")

        # 冲突
        if merged_data['conflicts']:
            report.append(f"\n⚠️ 检测到 {len(merged_data['conflicts'])} 个冲突:")
            for conflict in merged_data['conflicts']:
                report.append(f"  ✗ {conflict}")

        # 警告
        if merged_data['warnings']:
            report.append(f"\n⚠️ {len(merged_data['warnings'])} 个警告:")
            for warning in merged_data['warnings']:
                report.append(f"  ⚠ {warning}")

        # 摘要
        report.append(f"\n📊 摘要:\n{merged_data['summary']}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)


# 导入pandas用于timestamp
import pandas as pd
