"""
StateManagerV2 - 数据库驱动的状态管理器

使用 SQLite ,支持所有 8 个 Phase 的数据保存与加载。
"""
from typing import Any, Dict, Optional, List
from datetime import datetime
import json
import pandas as pd
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from database.engine import get_db_session
from database.models import (
    Project, ProjectStatus, Mission, ProjectState,
    DesignVariable, VariableType, ValueAttribute, OptimizationDirection, DVMMatrix,
    NSquaredDiagram, NSquaredNode, NSquaredEdge,
    UserModel, ModelType, ModelVersion,
    DesignAlternative, SimulationResult,
    SensitivityAnalysis, ParetoAnalysis, MCDMAnalysis
)

def parse_range_string(range_str: str, var_type: str) -> Dict[str, Any]:
    """
    解析范围字符串的后端兜底逻辑
    :param range_str: 用户输入的原始字符串，如 "10-20", "[10, 20]", "A, B, C"
    :param var_type: 变量类型 'continuous', 'discrete', 'categorical'
    :return: 包含 min, max, options 的字典
    """
    result = {'min': None, 'max': None, 'options': None}
    
    if not range_str or not isinstance(range_str, str):
        return result

    # 清理括号
    cleaned = range_str.strip().replace('[', '').replace(']', '').replace('(', '').replace(')', '')
    
    try:
        if var_type == 'continuous':
            # 尝试解析 "min-max" 格式
            if '-' in cleaned and ',' not in cleaned:
                parts = cleaned.split('-')
                if len(parts) == 2:
                    result['min'] = float(parts[0].strip())
                    result['max'] = float(parts[1].strip())
            # 尝试解析 "min, max" 格式
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if len(parts) >= 2:
                    vals = [float(p.strip()) for p in parts if p.strip()]
                    result['min'] = min(vals)
                    result['max'] = max(vals)
                    
        elif var_type == 'discrete':
            # 离散值通常逗号分隔
            if ',' in cleaned or '，' in cleaned:
                norm = cleaned.replace('，', ',')
                values = [float(v.strip()) for v in norm.split(',') if v.strip()]
                result['options'] = values
                if values:
                    result['min'] = min(values)
                    result['max'] = max(values)
            elif '-' in cleaned: # 假如用户写了 range 格式但选了离散
                 parts = cleaned.split('-')
                 if len(parts) == 2:
                    start, end = float(parts[0]), float(parts[1])
                    # 生成简单的整数序列作为 fallback
                    result['options'] = list(range(int(start), int(end)+1))

        elif var_type == 'categorical':
            # 分类变量
            norm = cleaned.replace('，', ',')
            if ',' in norm:
                result['options'] = [v.strip() for v in norm.split(',') if v.strip()]
            else:
                result['options'] = [norm.strip()]

    except Exception as e:
        print(f"⚠️ 后端解析 Range 失败: {range_str} ({e})")
    
    return result

class StateManagerV2:
    """
    使用 SQLAlchemy + SQLite 存储,自动创建或加载项目，支持完整的 8 Phase 工作流。
    """

    def __init__(self, project_name: str = "default_project"):
        """
        初始化状态管理器

        Args:
            project_name: 项目名称（如不存在则自动创建）
        """
        self.project_name = project_name
        self.project_id: Optional[int] = None
        self._ensure_project()

    def _ensure_project(self) -> None:
        """确保项目存在，如不存在则创建"""
        with get_db_session() as session:
            # 原代码: project = session.execute(stmt).scalar_one_or_none()
            # 修改为: scalars().all() 并手动处理重复
            
            stmt = select(Project).where(Project.name == self.project_name)
            projects = session.execute(stmt).scalars().all()

            if projects:
                # 情况1: 存在一个或多个项目
                project = projects[0]  # 总是取第一个
                
                # 如果发现多余的重复项，默默清理掉（自我修复）
                if len(projects) > 1:
                    for dup in projects[1:]:
                        session.delete(dup)
                    session.commit()
                    # print(f"自动修复: 删除了 {len(projects)-1} 个重复的 '{self.project_name}' 项目记录")
            else:
                # 情况2: 不存在，创建新项目
                project = Project(
                    name=self.project_name,
                    description=f"Auto-created project: {self.project_name}",
                    created_by="System",
                    status=ProjectStatus.ACTIVE
                )
                session.add(project)
                session.flush()

                # 创建关联的项目状态
                project_state = ProjectState(
                    project_id=project.id,
                    current_phase="phase1",
                    current_step=1,
                    step_statuses={}
                )
                session.add(project_state)
                session.commit()
            
            self.project_id = project.id

    # ==================== 核心接口方法 ====================

    def save(self, phase: str, key: str, value: Any) -> None:
        """
        保存数据到数据库

        Args:
            phase: 阶段名称（如 "phase1", "phase2"）
            key: 数据键（如 "design_variables", "value_attributes"）
            value: 要保存的数据（可能是 dict, list, DataFrame 等）
        """
        # 路由到对应的 Phase 处理器
        handler_map = {
            "phase1": self._save_phase1,
            "phase2": self._save_phase2,
            "phase3": self._save_phase3,
            "phase4": self._save_phase4,
            "phase5": self._save_phase5,
            "phase6": self._save_phase6,
            "phase7": self._save_phase7,
            "phase8": self._save_phase8,
        }

        handler = handler_map.get(phase)
        if handler:
            handler(key, value)
            self.log_activity(phase, "save", f"Saved {key}")
        else:
            raise ValueError(f"Unknown phase: {phase}")

    def load(self, phase: str, key: str, default: Any = None) -> Any:
        """
        从数据库加载数据

        Args:
            phase: 阶段名称
            key: 数据键
            default: 如果不存在则返回的默认值

        Returns:
            加载的数据（可能是 dict, list, DataFrame 等）
        """
        handler_map = {
            "phase1": self._load_phase1,
            "phase2": self._load_phase2,
            "phase3": self._load_phase3,
            "phase4": self._load_phase4,
            "phase5": self._load_phase5,
            "phase6": self._load_phase6,
            "phase7": self._load_phase7,
            "phase8": self._load_phase8,
        }

        handler = handler_map.get(phase)
        if handler:
            result = handler(key)
            return result if result is not None else default
        else:
            return default

    def get_all_phase_data(self, phase: str) -> Dict:
        """
        获取各阶段的所有数据
        """
        all_keys = {
            "phase1": [
                "design_variables", "value_attributes", "dvm_matrix", "mission", "ui_state"
            ],
            "phase2": [
                "n_squared_diagram", "components", "interfaces", "ui_state"
            ],
            "phase3": [
                "design_alternatives", "doe_config", "sampling_config", 
                "cartesian_engine", "ui_state" 
            ],
            "phase4": [
                "user_models", "perf_models_dict", 
                "utility_functions_dict", "weights_mau_code","ui_state"
            ],
            "phase5": [
                "simulation_results", "unified_results", "ui_state"
            ],
            "phase6": [
                "sensitivity_analysis", "constraints", "feasible_designs", 
                "constraint_config", "ui_state"
            ],
            "phase7": [
                "pareto_analysis", 
                "view_config", "ui_state"
            ],
            "phase8": [
                "mcdm_analysis", 
                "mcdm_config",
                "optimization_results", "ui_state"
            ],
        }

        keys = all_keys.get(phase, [])
        return {key: self.load(phase, key) for key in keys}
    
    def get_project_template(self) -> Dict:
        """
        生成一个包含所有Phase结构但内容为空的标准项目模板 (V2.0 格式)
        保持与 export_project 输出结构一致，确保可重新导入。
        """
        from datetime import datetime
        
        # 定义空的各阶段数据结构
        empty_phases = {
            "phase1": {
                "mission": {
                    "title": "", "description": "", 
                    "key_objectives": [], "value_proposition": ""
                },
                "design_variables": [],  # 预期格式: [{"name": "var1", "type": "continuous", ...}]
                "value_attributes": [],  # 预期格式: [{"name": "attr1", "direction": "maximize", ...}]
                "dvm_matrix": []         # V2格式 DVM矩阵通常是一个记录列表
            },
            "phase2": {
                "n_squared_diagram": {"nodes": [], "edges": []},
                "components": [],
                "interfaces": []
            },
            "phase3": {
                "design_alternatives": [],
                "doe_config": {"method": "full_factorial", "levels": {}},
                "sampling_config": {},
                "cartesian_engine": {}
            },
            "phase4": {
                "user_models": [], 
                "cost_model_code": "",
                "perf_models_dict": {},
                "utility_functions_dict": {},
                "weights_mau_code": "",
                "ui_state": {} # 预留UI状态
            },
            "phase5": {
                "simulation_results": [],
                "unified_results": [],
                "ui_state": {}
            },
            "phase6": {
                "sensitivity_analysis": {},
                "constraints": [],
                "feasible_designs": [],
                "constraint_config": {}
            },
            "phase7": {
                "pareto_analysis": {"pareto_front": [], "dominated_solutions": []},
                "view_config": {"x": None, "y": None, "z": None}
            },
            "phase8": {
                "mcdm_analysis": {},
                "mcdm_config": {},
                "optimization_results": {}
            }
        }

        # 组装 V2 标准包
        return {
            "version": "2.0",
            "format": "system_engineering_project",
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "project_name": "New Project Template",
                "last_modified": datetime.now().isoformat(),
                "exported_by": "System Engineering Platform v2.0",
                "export_notes": "标准空白模板"
            },
            "data": empty_phases,
            "validation": {
                "status": "template", 
                "note": "Empty template for new project initialization"
            }
        }

    # ==================== Phase 1: 问题定义 ====================

    def _save_phase1(self, key: str, value: Any) -> None:
        """保存 Phase 1 数据"""
        with get_db_session() as session:
            if key == "design_variables":
                self._save_design_variables(session, value)
            elif key == "value_attributes":
                self._save_value_attributes(session, value)
            elif key == "dvm_matrix":
                self._save_dvm_matrix(session, value)
            elif key == "mission":
                self._save_mission(session, value)
            elif key == "ui_state":
                self._save_to_step_status(session, "phase1_ui_state", value)

    def _load_phase1(self, key: str) -> Any:
        """加载 Phase 1 数据"""
        with get_db_session() as session:
            if key == "design_variables":
                return self._load_design_variables(session)
            elif key == "value_attributes":
                return self._load_value_attributes(session)
            elif key == "dvm_matrix":
                return self._load_dvm_matrix(session)
            elif key == "mission":
                return self._load_mission(session)
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase1_ui_state")
            return None

    def _save_design_variables(self, session: Session, data: Any) -> None:
        """保存设计变量"""
        # 删除现有数据
        session.query(DesignVariable).filter_by(project_id=self.project_id).delete()

        # 转换 DataFrame 为字典列表
        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            return

        # 插入新数据
        for record in records:
            # 1. 获取基础数据
            var_name = record.get('name', '')
            var_type = record.get('type', 'continuous')
            range_str = record.get('range', '') # 获取原始 range 字符串
            
            # 2. 优先使用传入的结构化数据
            val_min = record.get('min')
            val_max = record.get('max')
            val_options = record.get('values') or record.get('options')
            
            # 3. [核心修复] 如果结构化数据缺失，尝试后端兜底解析
            if (val_min is None and val_max is None and val_options is None) and range_str:
                parsed = parse_range_string(str(range_str), var_type)
                val_min = parsed['min']
                val_max = parsed['max']
                val_options = parsed['options']

            # 4. 序列化 options
            options_json = json.dumps(val_options) if val_options else None

            var = DesignVariable(
                project_id=self.project_id,
                name=var_name,
                variable_type=VariableType(var_type),
                range_min=val_min,
                range_max=val_max,
                options=options_json,
                unit=record.get('unit'),
                description=record.get('description')
            )
            session.add(var)

    def _load_design_variables(self, session: Session) -> pd.DataFrame:
        """加载设计变量为 DataFrame"""
        stmt = select(DesignVariable).where(DesignVariable.project_id == self.project_id)
        variables = session.execute(stmt).scalars().all()

        if not variables:
            return pd.DataFrame()

        records = []
        for var in variables:
            values_data = None
            if var.options:
                try:
                    values_data = json.loads(var.options) if isinstance(var.options, str) else var.options
                except (json.JSONDecodeError, TypeError):
                    values_data = None

            record = {
                'name': var.name,
                'type': var.variable_type.value,
                'min': var.range_min,
                'max': var.range_max,
                'values': values_data,
                'unit': var.unit,
                'description': var.description
            }
            records.append(record)

        return pd.DataFrame(records)

    def _save_value_attributes(self, session: Session, data: Any) -> None:
        """保存价值属性"""
        session.query(ValueAttribute).filter_by(project_id=self.project_id).delete()

        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            return

        for record in records:
            target_value = record.get('target')
            weight_value = record.get('weight', 1.0)
            final_weight = target_value if target_value is not None else weight_value

            attr = ValueAttribute(
                project_id=self.project_id,
                name=record.get('name', ''),
                unit=record.get('unit'),
                ideal_value=record.get('ideal_value'),
                worst_value=record.get('worst_value'),
                optimization_direction=OptimizationDirection(record.get('direction', 'maximize')),
                weight=final_weight,
                definition=record.get('definition')
            )
            session.add(attr)

    def _load_value_attributes(self, session: Session) -> pd.DataFrame:
        """加载价值属性为 DataFrame"""
        stmt = select(ValueAttribute).where(ValueAttribute.project_id == self.project_id)
        attributes = session.execute(stmt).scalars().all()

        if not attributes:
            return pd.DataFrame()

        records = []
        for attr in attributes:
            record = {
                'name': attr.name,
                'unit': attr.unit,
                'ideal_value': attr.ideal_value,
                'worst_value': attr.worst_value,
                'direction': attr.optimization_direction.value if attr.optimization_direction else None,
                'target': attr.weight,
                'definition': attr.definition
            }
            records.append(record)

        return pd.DataFrame(records)

    def _save_dvm_matrix(self, session: Session, data: Any) -> None:
        """保存 DVM 矩阵"""
        session.query(DVMMatrix).filter_by(project_id=self.project_id).delete()

        vars_stmt = select(DesignVariable).where(DesignVariable.project_id == self.project_id)
        variables = {v.name: v.id for v in session.execute(vars_stmt).scalars().all()}

        attrs_stmt = select(ValueAttribute).where(ValueAttribute.project_id == self.project_id)
        attributes = {a.name: a.id for a in session.execute(attrs_stmt).scalars().all()}

        if isinstance(data, pd.DataFrame):
            for var_name in data.index:
                if var_name not in variables:
                    continue
                var_id = variables[var_name]

                for attr_name in data.columns:
                    if attr_name not in attributes:
                        continue
                    attr_id = attributes[attr_name]

                    score = data.loc[var_name, attr_name]
                    if pd.notna(score):
                        dvm = DVMMatrix(
                            project_id=self.project_id,
                            design_variable_id=var_id,
                            value_attribute_id=attr_id,
                            influence_score=int(score)
                        )
                        session.add(dvm)

    def _load_dvm_matrix(self, session: Session) -> pd.DataFrame:
        """加载 DVM 矩阵为 DataFrame"""
        stmt = select(DVMMatrix).where(DVMMatrix.project_id == self.project_id)
        entries = session.execute(stmt).scalars().all()

        if not entries:
            return pd.DataFrame()

        vars_stmt = select(DesignVariable).where(DesignVariable.project_id == self.project_id)
        var_names = {v.id: v.name for v in session.execute(vars_stmt).scalars().all()}

        attrs_stmt = select(ValueAttribute).where(ValueAttribute.project_id == self.project_id)
        attr_names = {a.id: a.name for a in session.execute(attrs_stmt).scalars().all()}

        data = {}
        for entry in entries:
            var_name = var_names.get(entry.design_variable_id, f"Var_{entry.design_variable_id}")
            attr_name = attr_names.get(entry.value_attribute_id, f"Attr_{entry.value_attribute_id}")

            if var_name not in data:
                data[var_name] = {}
            data[var_name][attr_name] = entry.influence_score

        if not data:
            return pd.DataFrame()

        return pd.DataFrame(data).T


    def _save_mission(self, session: Session, data: Dict) -> None:
        """保存任务定义，并同步更新 Project 表元数据"""
        # 1. 尝试查找现有 Mission 记录
        stmt = select(Mission).where(Mission.project_id == self.project_id)
        mission = session.execute(stmt).scalar_one_or_none()

        if mission:
            # 更新现有记录
            if 'title' in data:
                mission.title = data['title']
            if 'description' in data:
                mission.description = data['description']
            if 'key_objectives' in data:
                mission.key_objectives = data['key_objectives']
            if 'value_proposition' in data:
                mission.value_proposition = data['value_proposition']
        else:
            # 创建新记录
            mission = Mission(
                project_id=self.project_id,
                title=data.get('title', ''),
                description=data.get('description', ''),
                key_objectives=data.get('key_objectives', []),
                value_proposition=data.get('value_proposition', '')
            )
            session.add(mission)
        
        # 显式标记修改 (针对 JSON 类型字段 key_objectives)
        flag_modified(mission, 'key_objectives')

        # ------------------------ 同步更新 Project 表 -----------------------------------------
        if self.project_id:
            # 查找对应的 Project 记录
            stmt_proj = select(Project).where(Project.id == self.project_id)
            project = session.execute(stmt_proj).scalar_one_or_none()
            
            if project:
                # 如果 mission 数据中有 title，则同步更新 project name
                if 'title' in data and data['title']:
                    project.name = data['title']
                
                # 如果 mission 数据中有 description，则同步更新 project description
                if 'description' in data:
                    project.description = data['description']
                
                # 记录日志 (可选)
                # print(f"🔄 已同步更新 Project 元数据: {project.name}")

    def _load_mission(self, session: Session) -> Dict:
        """加载任务定义"""
        stmt = select(Mission).where(Mission.project_id == self.project_id)
        mission = session.execute(stmt).scalar_one_or_none()

        if mission is None:
            return {}

        return {
            'title': mission.title,
            'description': mission.description,
            'key_objectives': mission.key_objectives,
            'value_proposition': mission.value_proposition
        }

    # ==================== Phase 2: 物理架构 ====================

    def _save_phase2(self, key: str, value: Any) -> None:
        """保存 Phase 2 数据"""
        with get_db_session() as session:
            if key == "n_squared_diagram":
                self._save_n_squared_diagram(session, value)
            elif key == "components":
                self._save_components(session, value)
            elif key == "interfaces":
                self._save_interfaces(session, value)
            elif key == "ui_state":
                self._save_to_step_status(session, "phase2_ui_state", value)

    def _load_phase2(self, key: str) -> Any:
        """加载 Phase 2 数据"""
        with get_db_session() as session:
            if key == "n_squared_diagram":
                return self._load_n_squared_diagram(session)
            elif key == "components":
                return self._load_components(session)
            elif key == "interfaces":
                return self._load_interfaces(session)
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase2_ui_state")
            return None

    def _save_n_squared_diagram(self, session: Session, data: Dict) -> None:
        """保存 N-squared 图表"""
        session.query(NSquaredDiagram).filter_by(project_id=self.project_id).delete()

        diagram = NSquaredDiagram(
            project_id=self.project_id,
            name=data.get('name', 'N-Squared Diagram'),
            description=data.get('description', ''),
            diagram_metadata=data.get('metadata', {})
        )
        session.add(diagram)
        session.flush()

        nodes_data = data.get('nodes', [])
        node_id_map = {}
        for node in nodes_data:
            db_node = NSquaredNode(
                diagram_id=diagram.id,
                node_id=node.get('id', ''),
                name=node.get('name', ''),
                description=node.get('description', ''),
                position=node.get('position', 0)
            )
            session.add(db_node)
            session.flush()
            node_id_map[node.get('id')] = db_node.id

        edges_data = data.get('edges', [])
        for edge in edges_data:
            source_id = node_id_map.get(edge.get('source'))
            target_id = node_id_map.get(edge.get('target'))

            if source_id and target_id:
                db_edge = NSquaredEdge(
                    diagram_id=diagram.id,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    interface_type=edge.get('type', ''),
                    description=edge.get('description', '')
                )
                session.add(db_edge)

    def _load_n_squared_diagram(self, session: Session) -> Dict:
        """加载 N-squared 图表"""
        stmt = select(NSquaredDiagram).where(NSquaredDiagram.project_id == self.project_id)
        diagram = session.execute(stmt).scalar_one_or_none()

        if diagram is None:
            return {}

        nodes_stmt = select(NSquaredNode).where(NSquaredNode.diagram_id == diagram.id)
        nodes = session.execute(nodes_stmt).scalars().all()

        db_id_to_node_id = {node.id: node.node_id for node in nodes}
        nodes_data = [
            {
                'id': node.node_id,
                'name': node.name,
                'description': node.description,
                'position': node.position
            }
            for node in nodes
        ]

        edges_stmt = select(NSquaredEdge).where(NSquaredEdge.diagram_id == diagram.id)
        edges = session.execute(edges_stmt).scalars().all()

        edges_data = [
            {
                'source': db_id_to_node_id.get(edge.source_node_id, ''),
                'target': db_id_to_node_id.get(edge.target_node_id, ''),
                'type': edge.interface_type,
                'description': edge.description
            }
            for edge in edges
        ]

        return {
            'name': diagram.name,
            'description': diagram.description,
            'metadata': diagram.diagram_metadata,
            'nodes': nodes_data,
            'edges': edges_data
        }

    def _save_components(self, session: Session, data: Any) -> None:
        """保存组件列表到 ProjectState"""
        self._save_to_step_status(session, 'phase2_components', data)

    def _load_components(self, session: Session) -> list:
        """从 ProjectState 加载组件列表"""
        return self._load_from_step_status(session, 'phase2_components', [])

    def _save_interfaces(self, session: Session, data: Any) -> None:
        """保存接口列表到 ProjectState"""
        self._save_to_step_status(session, 'phase2_interfaces', data)

    def _load_interfaces(self, session: Session) -> list:
        """从 ProjectState 加载接口列表"""
        return self._load_from_step_status(session, 'phase2_interfaces', [])

    # ==================== Phase 3: 设计空间生成  ====================


    def _save_phase3(self, key: str, value: Any) -> None:
        """保存 Phase 3 数据 (设计空间)"""
        with get_db_session() as session:
            if key == "design_alternatives" or key == "alternatives":
                self._save_design_alternatives(session, value)
            elif key == "doe_config":
                self._save_to_step_status(session, 'phase3_doe_config', value)
            elif key == "design_variables":
                self._save_design_variables(session, value)
            elif key == "sampling_config":
                self._save_to_step_status(session, "phase3_sampling_config", value)
            elif key == "cartesian_engine":
                self._save_to_step_status(session, "phase3_cartesian_engine", value)
            elif key == "ui_state":
                self._save_to_step_status(session, "phase3_ui_state", value)

    def _load_phase3(self, key: str) -> Any:
        """加载 Phase 3 数据 (设计空间)"""
        with get_db_session() as session:
            if key == "design_alternatives" or key == "alternatives":
                return self._load_design_alternatives(session)
            elif key == "doe_config":
                return self._load_from_step_status(session, 'phase3_doe_config')
            elif key == "design_variables":
                return self._load_design_variables(session)
            elif key == "sampling_config":
                return self._load_from_step_status(session, "phase3_sampling_config")
            elif key == "cartesian_engine":
                return self._load_from_step_status(session, "phase3_cartesian_engine")
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase3_ui_state")
            return None

    # ==================== Phase 4: 效用建模  ====================

    def _save_phase4(self, key: str, value: Any) -> None:
        """保存 Phase 4 数据"""
        with get_db_session() as session:
            if key == "user_models":
                self._save_user_models(session, value)
            elif key == "cost_model_code":
                self._save_cost_model_code(session, value) # 使用专用方法存入 UserModel
            elif key == "perf_models_dict":
                self._save_perf_models_dict(session, value) # 使用专用方法存入 UserModel
            elif key == "utility_functions_dict":
                self._save_utility_functions(session, value)
            elif key == "weights_mau_code":
                self._save_weights_mau_code(session, value) # 使用专用方法存入 UserModel
            elif key == "ui_state":
                self._save_to_step_status(session, "phase4_ui_state", value)

    def _load_phase4(self, key: str) -> Any:
        """加载 Phase 4 数据"""
        with get_db_session() as session:
            if key == "user_models":
                return self._load_user_models(session)
            elif key == "cost_model_code":
                return self._load_cost_model_code(session)
            elif key == "perf_models_dict":
                return self._load_perf_models_dict(session)
            elif key == "utility_functions_dict":
                return self._load_utility_functions(session)
            elif key == "weights_mau_code":
                return self._load_weights_mau_code(session)
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase4_ui_state")
            return None
    

    # ==================== Phase 4 Logic (Moved from P3 to P4) ====================

    def _save_user_models(self, session: Session, data: Any) -> None:
        """保存用户定义模型"""
        # 转换为列表格式
        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        elif isinstance(data, dict):
            records = [data]
        elif isinstance(data, list):
            records = data
        else:
            return

        for record in records:
            model_name = record.get('name', '')
            model_type_str = record.get('type', 'performance')

            # 查找现有模型
            stmt = select(UserModel).where(
                UserModel.project_id == self.project_id,
                UserModel.name == model_name
            )
            existing_model = session.execute(stmt).scalar_one_or_none()

            code_content = record.get('code', '')
            formula_content = record.get('formula', '')

            if existing_model:
                # 更新现有模型
                existing_model.model_type = ModelType(model_type_str)
                existing_model.description = record.get('description', '')
                existing_model.formula = formula_content
                existing_model.parameters = record.get('parameters', {})
                existing_model.code = code_content

                # 如果代码有变化,创建新版本
                if code_content and code_content != existing_model.code:
                    self._create_model_version(session, existing_model, code_content)
            else:
                # 创建新模型
                new_model = UserModel(
                    project_id=self.project_id,
                    name=model_name,
                    model_type=ModelType(model_type_str),
                    description=record.get('description', ''),
                    formula=formula_content,
                    parameters=record.get('parameters', {}),
                    code=code_content
                )
                session.add(new_model)
                session.flush()

                # 创建初始版本
                if code_content:
                    self._create_model_version(session, new_model, code_content, version="1.0")

    def _create_model_version(self, session: Session, model: UserModel, code: str, version: str = None) -> None:
        """创建模型版本"""
        if version is None:
            # 自动生成版本号
            stmt = select(ModelVersion).where(ModelVersion.model_id == model.id).order_by(ModelVersion.id.desc())
            latest_version = session.execute(stmt).scalar_one_or_none()

            if latest_version:
                major, minor = map(int, latest_version.version.split('.'))
                version = f"{major}.{minor + 1}"
            else:
                version = "1.0"

        # 将之前的活动版本设为非活动
        session.query(ModelVersion).filter_by(
            model_id=model.id,
            is_active=True
        ).update({'is_active': False})

        # 创建新版本
        new_version = ModelVersion(
            model_id=model.id,
            version=version,
            description=f"Auto-saved version {version}",
            code=code,
            is_active=True
        )
        session.add(new_version)

    def _load_user_models(self, session: Session) -> pd.DataFrame:
        """加载用户定义模型"""
        stmt = select(UserModel).where(UserModel.project_id == self.project_id)
        models = session.execute(stmt).scalars().all()

        if not models:
            return pd.DataFrame()

        records = []
        for model in models:
            record = {
                'name': model.name,
                'type': model.model_type.value,
                'description': model.description,
                'formula': model.formula,
                'parameters': model.parameters,
                'code': model.code
            }
            records.append(record)

        return pd.DataFrame(records)

    def _save_cost_model_code(self, session: Session, code: str) -> None:
        """保存成本模型代码"""
        self._save_single_model_code(session, "cost_model", "cost", code)

    def _load_cost_model_code(self, session: Session) -> Optional[str]:
        """加载成本模型代码"""
        stmt = select(UserModel).where(
            UserModel.project_id == self.project_id,
            UserModel.name == "cost_model"
        )
        model = session.execute(stmt).scalar_one_or_none()
        return model.code if model else None

    def _save_perf_models_dict(self, session: Session, models_dict: Dict[str, str]) -> None:
        """保存性能模型字典到 UserModel 表"""
        # 1. 清理旧的性能模型 (按类型和命名约定)
        session.query(UserModel).filter(
            UserModel.project_id == self.project_id,
            UserModel.model_type == ModelType('performance'),
            UserModel.name.like('calculate_%') # 假设函数名都以 calculate_ 开头
        ).delete(synchronize_session=False)

        if not models_dict:
            return

        # 2. 插入新记录
        for metric_name, code in models_dict.items():
            # 确保存储时的名称与加载时一致
            # 前端通常传的是原始名称，这里我们存为 user_model 记录
            model = UserModel(
                project_id=self.project_id,
                name=f"perf_{metric_name}", # 使用前缀区分
                model_type=ModelType('performance'),
                description=f"Performance model for {metric_name}",
                code=code,
                formula="",
                parameters={}
            )
            session.add(model)

    def _load_perf_models_dict(self, session: Session) -> Optional[Dict[str, str]]:
        """从 UserModel 表加载性能模型字典"""
        stmt = select(UserModel).where(
            UserModel.project_id == self.project_id,
            UserModel.model_type == ModelType('performance'),
            UserModel.name.like('perf_%')
        )
        models = session.execute(stmt).scalars().all()

        if not models:
            return {}

        result = {}
        for model in models:
            # 去除前缀还原 Key
            original_name = model.name[5:] if model.name.startswith("perf_") else model.name
            result[original_name] = model.code

        return result
    
    def _save_utility_functions(self, session: Session, data: Any) -> None:
        """保存效用函数 (存入 step_statuses JSON Blob)"""
        # 因为效用函数是一个字典集合，存为 JSON 配置最简单
        self._save_to_step_status(session, "phase4_utility_functions", data)

    def _load_utility_functions(self, session: Session) -> Any:
        """加载效用函数"""
        return self._load_from_step_status(session, "phase4_utility_functions", {})

    def _save_weights_mau_code(self, session: Session, code: str) -> None:
        """保存权重和MAU计算代码 (存入 UserModel)"""
        self._save_single_model_code(session, "phase4_weights_mau", "weights", code)

    def _load_weights_mau_code(self, session: Session) -> Optional[str]:
        """加载权重和MAU计算代码"""
        return self._load_single_model_code(session, "phase4_weights_mau")

    # === 通用模型存储辅助函数 (优化代码复用) ===

    def _save_single_model_code(self, session: Session, name: str, mtype: str, code: str):
        """通用：保存单个代码块到 UserModel 表"""
        if code is None: 
            return
            
        # 查找是否存在
        stmt = select(UserModel).where(UserModel.project_id == self.project_id, UserModel.name == name)
        model = session.execute(stmt).scalar_one_or_none()
        
        # 数据库模型类型枚举映射
        db_type = mtype if mtype in ['cost', 'performance'] else 'performance'
        
        if model:
            # 更新
            model.code = code
            model.model_type = ModelType(db_type)
        else:
            # 创建
            model = UserModel(
                project_id=self.project_id, 
                name=name, 
                model_type=ModelType(db_type), 
                code=code, 
                description=f"{mtype} model"
            )
            session.add(model)

    def _load_single_model_code(self, session: Session, name: str) -> Optional[str]:
        """通用：从 UserModel 表加载单个代码块"""
        stmt = select(UserModel).where(UserModel.project_id == self.project_id, UserModel.name == name)
        model = session.execute(stmt).scalar_one_or_none()
        return model.code if model else None

    # ==================== Phase 3 Logic  ====================

    def _save_design_alternatives(self, session: Session, data: Any) -> None:
        """保存设计方案"""
        # 清空现有方案
        session.query(DesignAlternative).filter_by(project_id=self.project_id).delete()

        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            return

        for record in records:
            # 过滤掉非设计变量的字段（如design_id）以避免存入design_vector
            design_vector = {k: v for k, v in record.items() if k != 'design_id'}
            
            alternative = DesignAlternative(
                project_id=self.project_id,
                name=record.get('name', f"Alt_{record.get('design_id', len(records))}"),
                design_vector=design_vector,
                generation_method=record.get('generation_method', 'auto')
            )
            session.add(alternative)

    def _load_design_alternatives(self, session: Session) -> pd.DataFrame:
        """加载设计方案"""
        stmt = select(DesignAlternative).where(DesignAlternative.project_id == self.project_id)
        alternatives = session.execute(stmt).scalars().all()

        if not alternatives:
            return pd.DataFrame()

        records = []
        for alt in alternatives:
            record = alt.design_vector.copy()
            record['design_id'] = alt.id  # 将DB ID作为design_id
            record['name'] = alt.name
            records.append(record)

        return pd.DataFrame(records)

    def _save_doe_config(self, session: Session, data: Dict) -> None:
        """保存 DOE 配置到 Step Status (Phase 3)"""
        # 🔧 2025-12-26 修复：键名改为 phase3_doe_config
        self._save_to_step_status(session, 'phase3_doe_config', data)

    def _load_doe_config(self, session: Session) -> Optional[Dict]:
        """加载 DOE 配置 (Phase 3)"""
        return self._load_from_step_status(session, 'phase3_doe_config')

    # ==================== Phase 5: 仿真评估 ====================

    def _save_phase5(self, key: str, value: Any) -> None:
        """保存 Phase 5 数据"""
        with get_db_session() as session:
            if key == "simulation_results":
                # 保存到结构化表 (可选，用于归档)
                self._save_simulation_results(session, value)
            elif key == "unified_results":
                # 核心：将计算结果保存为 JSON Blob，以支持动态列结构
                # 能够完美恢复 DataFrame
                if isinstance(value, pd.DataFrame):
                    data_to_save = value.to_dict('records')
                else:
                    data_to_save = value
                self._save_to_step_status(session, "phase5_unified_results", data_to_save)
            elif key == "ui_state":
                # 核心：保存回归分析配置、图表选择等
                self._save_to_step_status(session, "phase5_ui_state", value)

    def _load_phase5(self, key: str) -> Any:
        """加载 Phase 5 数据"""
        with get_db_session() as session:
            if key == "simulation_results":
                return self._load_simulation_results(session)
            elif key == "unified_results":
                # 从 JSON Blob 恢复
                data = self._load_from_step_status(session, "phase5_unified_results")
                if data:
                    return pd.DataFrame(data)
                return None
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase5_ui_state")
            return None

    def _save_simulation_results(self, session: Session, data: Any) -> None:
        """
        保存仿真结果到 SimulationResult 表
        支持传入 DataFrame 或 List[Dict] (unified_results 格式)
        """
        # 1. 数据格式标准化
        records = []
        if isinstance(data, pd.DataFrame):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict) and 'data' in data:
            records = data['data']
        
        if not records:
            return

        # 2. 获取 DesignAlternative ID 映射
        stmt = select(DesignAlternative).where(DesignAlternative.project_id == self.project_id)
        alternatives = {alt.id: alt for alt in session.execute(stmt).scalars().all()} # Map ID to Obj
        
        # 也可以建立 Name 到 ID 的映射作为备用
        alt_name_map = {alt.name: alt.id for alt in alternatives.values()}

        # 3. 清除旧结果 (可选，取决于是否增量更新，这里选择覆盖以保持一致)
        session.query(SimulationResult).filter(
            SimulationResult.design_alternative_id.in_(alternatives.keys())
        ).delete(synchronize_session=False)

        # 4. 插入新数据
        for row in records:
            design_id = row.get('design_id')
            alt_id = None
            
            # 尝试匹配 DesignAlternative
            if design_id is not None and design_id in alternatives:
                alt_id = design_id
            elif row.get('name') in alt_name_map:
                alt_id = alt_name_map[row.get('name')]
            
            # 如果找不到对应的 DesignAlternative，可能需要新建或跳过
            # 这里假设 Phase 3 已经生成了 DesignAlternative
            if not alt_id:
                continue

            # 分离指标：成本、MAU、其他性能
            cost_metrics = {}
            perf_metrics = {}
            utility_score = row.get('MAU', 0.0)
            
            for k, v in row.items():
                if k in ['design_id', 'name', 'MAU']:
                    continue
                if 'cost' in k.lower() or 'price' in k.lower():
                    cost_metrics[k] = v
                else:
                    perf_metrics[k] = v

            result = SimulationResult(
                design_alternative_id=alt_id,
                performance_metrics=perf_metrics,
                cost_metrics=cost_metrics,
                utility_score=utility_score,
                normalized_metrics={} # 暂留空或后续计算
            )
            session.add(result)

    def _load_simulation_results(self, session: Session) -> pd.DataFrame:
        """从 SimulationResult 表加载并重组为 DataFrame"""
        stmt = select(SimulationResult).join(DesignAlternative).where(
            DesignAlternative.project_id == self.project_id
        )
        results = session.execute(stmt).scalars().all()

        if not results:
            return pd.DataFrame()

        flattened_data = []
        for res in results:
            row = {'design_id': res.design_alternative_id, 'MAU': res.utility_score}
            # 展平字典
            if res.performance_metrics:
                row.update(res.performance_metrics)
            if res.cost_metrics:
                row.update(res.cost_metrics)
            flattened_data.append(row)

        return pd.DataFrame(flattened_data)

    def _save_unified_results(self, session: Session, data: Any) -> None:
        """保存统一结果"""
        # 如果是 DataFrame，转为 dict 列表
        serialized_data = data
        if isinstance(data, pd.DataFrame):
            serialized_data = data.to_dict('records')
        
        self._save_to_step_status(session, 'phase5_unified_results', serialized_data)

    def _load_unified_results(self, session: Session) -> pd.DataFrame:
        """加载统一结果"""
        data = self._load_from_step_status(session, 'phase5_unified_results', [])
        return pd.DataFrame(data) if data else pd.DataFrame()

# ==================== Phase 6: 敏感性分析 ====================

    def _save_phase6(self, key: str, value: Any) -> None:
        """保存 Phase 6 数据"""
        with get_db_session() as session:
            if key == "sensitivity_analysis":
                self._save_to_step_status(session, "phase6_sensitivity", value)
            elif key == "constraints":
                self._save_to_step_status(session, "phase6_constraints", value)
            elif key == "feasible_designs":
                self._save_to_step_status(session, "phase6_feasible_designs", value)
            elif key == "constraint_config":
                self._save_to_step_status(session, "phase6_config", value)
            elif key == "ui_state":
                self._save_to_step_status(session, "phase6_ui_state", value)

    def _load_phase6(self, key: str) -> Any:
        """加载 Phase 6 数据"""
        with get_db_session() as session:
            if key == "sensitivity_analysis":
                return self._load_from_step_status(session, "phase6_sensitivity")
            elif key == "constraints":
                return self._load_from_step_status(session, "phase6_constraints")
            elif key == "feasible_designs":
                return self._load_from_step_status(session, "phase6_feasible_designs")
            elif key == "constraint_config":
                return self._load_from_step_status(session, "phase6_config")
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase6_ui_state")
            return None

    def _save_sensitivity_analysis(self, session: Session, data: Any) -> None:
        """保存敏感性分析结果"""
        session.query(SensitivityAnalysis).filter_by(project_id=self.project_id).delete()

        if isinstance(data, dict):
            records = [data]
        elif isinstance(data, list):
            records = data
        else:
            return

        for record in records:
            analysis = SensitivityAnalysis(
                project_id=self.project_id,
                analysis_type=record.get('analysis_type', 'local'),
                variable_name=record.get('variable_name', ''),
                results=record.get('results', {}),
                tornado_data=record.get('tornado_data', {})
            )
            session.add(analysis)

    def _load_sensitivity_analysis(self, session: Session) -> Dict:
        """加载敏感性分析结果"""
        stmt = select(SensitivityAnalysis).where(SensitivityAnalysis.project_id == self.project_id)
        analyses = session.execute(stmt).scalars().all()

        if not analyses:
            return {}

        if len(analyses) == 1:
            return {
                'analysis_type': analyses[0].analysis_type,
                'variable_name': analyses[0].variable_name,
                'results': analyses[0].results,
                'tornado_data': analyses[0].tornado_data
            }
        else:
            return {
                'analyses': [
                    {
                        'analysis_type': a.analysis_type,
                        'variable_name': a.variable_name,
                        'results': a.results,
                        'tornado_data': a.tornado_data
                    }
                    for a in analyses
                ]
            }

    def _save_constraints(self, session: Session, data: Any) -> None:
        """保存约束配置"""
        session.query(SensitivityAnalysis).filter_by(
            project_id=self.project_id,
            analysis_type='__meta__constraints__'
        ).delete()

        if not data:
            return

        constraint_record = SensitivityAnalysis(
            project_id=self.project_id,
            analysis_type='__meta__constraints__',
            variable_name='constraints_config',
            results=data if isinstance(data, list) else [data],
            tornado_data={}
        )
        session.add(constraint_record)

    def _load_constraints(self, session: Session) -> list:
        """加载约束配置"""
        stmt = select(SensitivityAnalysis).where(
            SensitivityAnalysis.project_id == self.project_id,
            SensitivityAnalysis.analysis_type == '__meta__constraints__'
        )
        record = session.execute(stmt).scalar_one_or_none()
        return record.results if record and isinstance(record.results, list) else []

    def _save_feasible_designs(self, session: Session, data: Any) -> None:
        """保存可行设计"""
        session.query(SensitivityAnalysis).filter_by(
            project_id=self.project_id,
            analysis_type='__meta__feasible_designs__'
        ).delete()

        if data is None:
            return

        if isinstance(data, pd.DataFrame):
            feasible_data = data.to_dict('records')
        elif isinstance(data, list):
            feasible_data = data
        else:
            return

        feasible_record = SensitivityAnalysis(
            project_id=self.project_id,
            analysis_type='__meta__feasible_designs__',
            variable_name='feasible_designs_data',
            results={'designs': feasible_data},
            tornado_data={}
        )
        session.add(feasible_record)

    def _load_feasible_designs(self, session: Session) -> pd.DataFrame:
        """加载可行设计"""
        stmt = select(SensitivityAnalysis).where(
            SensitivityAnalysis.project_id == self.project_id,
            SensitivityAnalysis.analysis_type == '__meta__feasible_designs__'
        )
        record = session.execute(stmt).scalar_one_or_none()

        if record is None:
            return pd.DataFrame()

        designs_data = record.results.get('designs', []) if isinstance(record.results, dict) else []
        return pd.DataFrame(designs_data) if designs_data else pd.DataFrame()

    # ==================== Phase 7: 帕累托分析 ====================

    def _save_phase7(self, key: str, value: Any) -> None:
        """保存 Phase 7 数据"""
        with get_db_session() as session:
            if key == "pareto_designs":
                self._save_to_step_status(session, "phase7_pareto_designs", value)
            elif key == "view_config": 
                self._save_to_step_status(session, "phase7_view_config", value)
            elif key == "ui_state":
                self._save_to_step_status(session, "phase7_ui_state", value)

    def _load_phase7(self, key: str) -> Any:
        """加载 Phase 7 数据"""
        with get_db_session() as session:
            if key == "pareto_designs":
                return self._load_from_step_status(session, "phase7_pareto_designs")
            elif key == "view_config":
                return self._load_from_step_status(session, "phase7_view_config")
            elif key == "ui_state":
                return self._load_from_step_status(session, "phase7_ui_state")
            return None

    def _save_pareto_analysis(self, session: Session, data: Dict) -> None:
        """保存帕累托分析结果"""
        session.query(ParetoAnalysis).filter_by(project_id=self.project_id).delete()

        analysis = ParetoAnalysis(
            project_id=self.project_id,
            pareto_front=data.get('pareto_front', []),
            dominated_solutions=data.get('dominated_solutions', []),
            objective_values=data.get('objective_values', {})
        )
        session.add(analysis)

    def _load_pareto_analysis(self, session: Session) -> Dict:
        """加载帕累托分析结果"""
        stmt = select(ParetoAnalysis).where(ParetoAnalysis.project_id == self.project_id)
        analysis = session.execute(stmt).scalar_one_or_none()

        if analysis is None:
            return {}

        return {
            'pareto_front': analysis.pareto_front,
            'dominated_solutions': analysis.dominated_solutions,
            'objective_values': analysis.objective_values
        }

    # ==================== Phase 8: 多准则决策 ====================

    def _save_phase8(self, key: str, value: Any) -> None:
        """保存 Phase 8 数据"""
        with get_db_session() as session:
            if key == "mcdm_analysis":
                self._save_mcdm_analysis(session, value)
            # 保存MCDM配置（权重、方法等）
            elif key == "mcdm_config":
                self._save_to_step_status(session, "phase8_mcdm_config", value)
            # 保存反向优化结果
            elif key == "optimization_results":
                self._save_to_step_status(session, "phase8_optimization_results", value)

    def _load_phase8(self, key: str) -> Any:
        """加载 Phase 8 数据"""
        with get_db_session() as session:
            if key == "mcdm_analysis":
                return self._load_mcdm_analysis(session)
            # 加载MCDM配置
            elif key == "mcdm_config":
                return self._load_from_step_status(session, "phase8_mcdm_config")
            # 加载反向优化结果
            elif key == "optimization_results":
                return self._load_from_step_status(session, "phase8_optimization_results")
            return None

    def _save_mcdm_analysis(self, session: Session, data: Dict) -> None:
        """保存多准则决策分析结果"""
        session.query(MCDMAnalysis).filter_by(project_id=self.project_id).delete()

        analysis = MCDMAnalysis(
            project_id=self.project_id,
            method=data.get('method', 'TOPSIS'),
            weights=data.get('weights', {}),
            rankings=data.get('rankings', []),
            scores=data.get('scores', {})
        )
        session.add(analysis)

    def _load_mcdm_analysis(self, session: Session) -> Dict:
        """加载多准则决策分析结果"""
        stmt = select(MCDMAnalysis).where(MCDMAnalysis.project_id == self.project_id)
        analysis = session.execute(stmt).scalar_one_or_none()

        if analysis is None:
            return {}

        return {
            'method': analysis.method,
            'weights': analysis.weights,
            'rankings': analysis.rankings,
            'scores': analysis.scores
        }

    # ==================== 通用辅助功能 ====================

    def _save_to_step_status(self, session: Session, key: str, value: Any) -> None:
        """通用：保存数据到 ProjectState 的 step_statuses JSON 字段"""
        if value is None:
            return

        stmt = select(ProjectState).where(ProjectState.project_id == self.project_id)
        project_state = session.execute(stmt).scalar_one_or_none()

        if project_state:
            if project_state.step_statuses is None:
                project_state.step_statuses = {}
            project_state.step_statuses[key] = value
            flag_modified(project_state, 'step_statuses')
        else:
            # 如果 ProjectState 不存在，理论上在 _ensure_project 已创建，但做个保险
            project_state = ProjectState(
                project_id=self.project_id,
                current_phase="unknown",
                current_step=1,
                step_statuses={key: value}
            )
            session.add(project_state)

    def _load_from_step_status(self, session: Session, key: str, default: Any = None) -> Any:
        """通用：从 ProjectState 的 step_statuses JSON 字段加载数据"""
        stmt = select(ProjectState).where(ProjectState.project_id == self.project_id)
        project_state = session.execute(stmt).scalar_one_or_none()

        if project_state and project_state.step_statuses:
            return project_state.step_statuses.get(key, default)
        return default

    def log_activity(self, phase: str, action: str, description: str) -> None:
        """记录活动日志"""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] {phase} | {action} | {description}")

    def validate_data_flow(self) -> Dict:
        """验证数据流完整性"""
        validation = {
            'phase1': {'required': ['mission', 'design_variables', 'value_attributes'], 'status': 'unknown'},
            'phase2': {'required': ['n_squared_diagram'], 'status': 'unknown'},
            # Phase 3 现在是设计空间
            'phase3': {'required': ['design_alternatives'], 'status': 'unknown'},
            # Phase 4 现在是用户模型
            'phase4': {'required': ['user_models'], 'status': 'unknown'},
            'phase5': {'required': ['simulation_results'], 'status': 'unknown'},
            'phase6': {'required': ['sensitivity_analysis'], 'status': 'unknown'},
            'phase7': {'required': ['pareto_analysis'], 'status': 'unknown'},
            'phase8': {'required': ['mcdm_analysis'], 'status': 'unknown'}
        }

        for phase, requirements in validation.items():
            missing = []
            for key in requirements['required']:
                value = self.load(phase, key)
                if value is None:
                    missing.append(key)
                elif isinstance(value, pd.DataFrame) and value.empty:
                    missing.append(key)
                elif isinstance(value, dict) and not value:
                    missing.append(key)
                elif isinstance(value, list) and not value:
                    missing.append(key)

            if not missing:
                validation[phase]['status'] = 'complete'
            else:
                validation[phase]['status'] = 'incomplete'
                validation[phase]['missing'] = missing

        return validation

    def export_to_json(self, filepath: str) -> None:
        """导出项目数据为 JSON"""
        export_data = {
            'project_name': self.project_name,
            'export_time': datetime.now().isoformat(),
            'phases': {}
        }

        for phase in ['phase1', 'phase2', 'phase3', 'phase4', 'phase5', 'phase6', 'phase7', 'phase8']:
            export_data['phases'][phase] = self.get_all_phase_data(phase)

        def convert_dataframes(obj):
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict('records')
            elif isinstance(obj, dict):
                return {k: convert_dataframes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_dataframes(item) for item in obj]
            else:
                return obj

        export_data = convert_dataframes(export_data)

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    def import_from_json(self, filepath: str) -> None:
        """从 JSON 导入项目数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            import_data = json.load(f)

        phases = import_data.get('phases', {})
        for phase, phase_data in phases.items():
            for key, value in phase_data.items():
                if value:
                    self.save(phase, key, value)

    def create_snapshot(self, snapshot_name: str = None) -> str:
        """创建项目快照"""
        if snapshot_name is None:
            snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        snapshot_path = f"snapshots/{self.project_name}/{snapshot_name}.json"
        self.export_to_json(snapshot_path)
        return snapshot_path

    def restore_snapshot(self, snapshot_name: str) -> bool:
        """恢复项目快照"""
        snapshot_path = f"snapshots/{self.project_name}/{snapshot_name}.json"
        if not Path(snapshot_path).exists():
            return False

        self.import_from_json(snapshot_path)
        return True

    def reset_all(self) -> None:
        """重置所有Phase数据到初始状态"""
        with get_db_session() as session:
            # Phase 1
            session.query(DesignVariable).filter_by(project_id=self.project_id).delete()
            session.query(ValueAttribute).filter_by(project_id=self.project_id).delete()
            session.query(DVMMatrix).filter_by(project_id=self.project_id).delete()
            session.query(Mission).filter_by(project_id=self.project_id).delete()

            # Phase 2
            session.query(NSquaredDiagram).filter_by(project_id=self.project_id).delete()

            # Phase 3 (Design Space - Swapped)
            session.query(DesignAlternative).filter_by(project_id=self.project_id).delete()

            # Phase 4 (Models - Swapped)
            session.query(UserModel).filter_by(project_id=self.project_id).delete()

            # Phase 6, 7, 8
            session.query(SensitivityAnalysis).filter_by(project_id=self.project_id).delete()
            session.query(ParetoAnalysis).filter_by(project_id=self.project_id).delete()
            session.query(MCDMAnalysis).filter_by(project_id=self.project_id).delete()

            # Reset Project State
            stmt = select(ProjectState).where(ProjectState.project_id == self.project_id)
            project_state = session.execute(stmt).scalar_one_or_none()
            if project_state:
                project_state.current_phase = "phase1"
                project_state.current_step = 1
                project_state.step_statuses = {}

            session.commit()

        self.log_activity('system', 'reset_all', "重置所有Phase数据到初始状态")
        print("✅ StateManagerV2已重置到初始状态")