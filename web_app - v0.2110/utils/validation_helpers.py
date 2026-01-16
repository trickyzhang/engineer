"""
Pydantic 验证错误处理工具

提供友好的错误消息格式化和 Dash Alert 组件生成功能。
"""
from typing import List, Dict, Any
from pydantic import ValidationError
import dash_bootstrap_components as dbc
from dash import html


def format_validation_error(error: ValidationError) -> List[Dict[str, Any]]:
    """
    格式化 Pydantic 验证错误为用户友好的消息列表

    Args:
        error: Pydantic ValidationError 对象

    Returns:
        格式化的错误消息列表，每个错误包含 field 和 message

    Example:
        >>> from pydantic import ValidationError
        >>> from database.schemas import DesignVariableCreate
        >>> try:
        ...     var = DesignVariableCreate(project_id=1, name="", variable_type="invalid")
        ... except ValidationError as e:
        ...     errors = format_validation_error(e)
        ...     # [{'field': 'name', 'message': '字段不能为空'},
        ...     #  {'field': 'variable_type', 'message': '变量类型必须是...'}]
    """
    formatted_errors = []

    for err in error.errors():
        field_path = " → ".join(str(loc) for loc in err['loc'])
        error_type = err['type']
        error_msg = err['msg']

        # 根据错误类型生成友好的中文消息
        if error_type == 'string_too_short':
            message = f"字段不能为空"
        elif error_type == 'string_too_long':
            max_length = err.get('ctx', {}).get('max_length', '未知')
            message = f"字段长度不能超过 {max_length} 个字符"
        elif error_type == 'greater_than_equal':
            limit = err.get('ctx', {}).get('ge', '未知')
            message = f"值必须大于或等于 {limit}"
        elif error_type == 'less_than_equal':
            limit = err.get('ctx', {}).get('le', '未知')
            message = f"值必须小于或等于 {limit}"
        elif error_type == 'value_error':
            # 自定义验证错误（如变量类型、DVM评分）
            message = error_msg.replace('Value error, ', '')
        elif error_type == 'missing':
            message = "此字段为必填项"
        elif error_type == 'type_error':
            expected_type = err.get('ctx', {}).get('expected_type', '正确类型')
            message = f"字段类型错误，期望: {expected_type}"
        else:
            # 其他错误，使用原始消息
            message = error_msg

        formatted_errors.append({
            'field': field_path,
            'message': message,
            'type': error_type
        })

    return formatted_errors


def create_validation_alert(
    errors: List[Dict[str, Any]],
    color: str = "danger",
    dismissible: bool = True
) -> dbc.Alert:
    """
    创建 Dash Bootstrap Alert 组件显示验证错误

    Args:
        errors: 格式化的错误消息列表（来自 format_validation_error）
        color: Alert 颜色（danger, warning, info, success）
        dismissible: 是否可关闭

    Returns:
        dbc.Alert 组件

    Example:
        >>> from pydantic import ValidationError
        >>> from database.schemas import DesignVariableCreate
        >>> try:
        ...     var = DesignVariableCreate(project_id=1, name="", variable_type="invalid")
        ... except ValidationError as e:
        ...     errors = format_validation_error(e)
        ...     alert = create_validation_alert(errors)
        ...     # 返回可以直接在 Dash 布局中使用的 Alert 组件
    """
    if not errors:
        return dbc.Alert(
            "没有验证错误",
            color="success",
            dismissible=dismissible
        )

    # 创建错误列表
    error_items = []
    for err in errors:
        error_items.append(
            html.Li([
                html.Strong(f"{err['field']}: "),
                html.Span(err['message'])
            ])
        )

    # 创建 Alert 组件
    alert = dbc.Alert(
        [
            html.H5("❌ 数据验证失败", className="alert-heading"),
            html.P("请检查以下字段："),
            html.Ul(error_items, className="mb-0")
        ],
        color=color,
        dismissible=dismissible,
        className="mb-3"
    )

    return alert


def create_success_alert(message: str = "✅ 数据保存成功！") -> dbc.Alert:
    """
    创建成功提示 Alert

    Args:
        message: 成功消息

    Returns:
        dbc.Alert 组件
    """
    return dbc.Alert(
        message,
        color="success",
        dismissible=True,
        duration=3000,  # 3秒后自动消失
        className="mb-3"
    )


def validate_and_create_alert(
    schema_class,
    data: Dict[str, Any]
) -> tuple[Any, dbc.Alert]:
    """
    验证数据并返回 Schema 实例和 Alert 组件

    这是一个便捷函数，用于在 Dash 回调中快速验证数据。

    Args:
        schema_class: Pydantic Schema 类
        data: 要验证的数据字典

    Returns:
        (schema_instance, alert) 元组
        - 如果验证成功，返回 (实例, 成功Alert)
        - 如果验证失败，返回 (None, 错误Alert)

    Example:
        >>> from database.schemas import DesignVariableCreate
        >>>
        >>> @app.callback(...)
        >>> def save_design_variable(n_clicks, name, var_type, min_val, max_val):
        ...     if not n_clicks:
        ...         return no_update
        ...
        ...     data = {
        ...         'project_id': 1,
        ...         'name': name,
        ...         'variable_type': var_type,
        ...         'range_min': min_val,
        ...         'range_max': max_val
        ...     }
        ...
        ...     # 验证数据
        ...     var, alert = validate_and_create_alert(DesignVariableCreate, data)
        ...
        ...     if var is None:
        ...         return alert  # 返回错误提示
        ...
        ...     # 保存到数据库...
        ...     return create_success_alert("设计变量保存成功！")
    """
    try:
        # 尝试创建 Schema 实例（会自动验证）
        instance = schema_class(**data)

        # 验证成功
        success_alert = create_success_alert("✅ 数据验证通过")
        return instance, success_alert

    except ValidationError as e:
        # 验证失败
        errors = format_validation_error(e)
        error_alert = create_validation_alert(errors)
        return None, error_alert


# ============ 使用示例 ============

def example_usage():
    """
    使用示例（仅供参考，不会被执行）
    """
    from database.schemas import DesignVariableCreate, DVMMatrixUpdate
    from pydantic import ValidationError

    # ========== 示例 1: 设计变量验证 ==========
    print("=" * 60)
    print("示例 1: 设计变量验证")
    print("=" * 60)

    try:
        # 尝试创建一个无效的设计变量
        var = DesignVariableCreate(
            project_id=1,
            name="",  # 空名称（无效）
            variable_type="invalid_type",  # 无效类型
            range_min=100.0,
            range_max=50.0  # max < min（无效）
        )
    except ValidationError as e:
        errors = format_validation_error(e)
        print("\n格式化的错误:")
        for err in errors:
            print(f"  - {err['field']}: {err['message']}")

        # 创建 Alert 组件
        alert = create_validation_alert(errors)
        print(f"\nAlert 组件已创建: {type(alert)}")

    # ========== 示例 2: DVM 矩阵验证 ==========
    print("\n" + "=" * 60)
    print("示例 2: DVM 矩阵评分验证")
    print("=" * 60)

    try:
        # 尝试使用无效评分
        dvm = DVMMatrixUpdate(influence_score=5)  # 必须是 0/1/3/9
    except ValidationError as e:
        errors = format_validation_error(e)
        print("\n格式化的错误:")
        for err in errors:
            print(f"  - {err['field']}: {err['message']}")

    # ========== 示例 3: 便捷函数 ==========
    print("\n" + "=" * 60)
    print("示例 3: 使用便捷函数")
    print("=" * 60)

    data = {
        'project_id': 1,
        'name': '长度',
        'variable_type': 'continuous',
        'range_min': 0.0,
        'range_max': 100.0
    }

    var, alert = validate_and_create_alert(DesignVariableCreate, data)

    if var:
        print(f"\n✅ 验证成功: {var.name}")
    else:
        print("\n❌ 验证失败")


if __name__ == "__main__":
    # 运行示例
    example_usage()
