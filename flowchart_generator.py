# Для коректної роботи з інтерфейсом, цей код має бути збережений в файлі flowchart_generator.py

# Налаштування за замовчуванням
global_settings = {
    "node_fontsize": 16,
    "edge_fontsize": 16,
    "cluster_fontsize": 20,
    "node_height": 1.0,
    "node_width": 1.5,
    "edge_penwidth": 2,
    "node_penwidth": 2,
    "cluster_margin": 45,
    "edge_arrows": "normal",
    "loopback_arrows": "normal",
    "nodesep": 0,
    "width_factor": 16,  # Встановити значення ширини тексту за замовчуванням 1s6
    "start_end_height": 0.5,
    "special_shape_width": 2.0,
    "loop_edge_weight": 55,
    "edge_weight": 50,
    "online_mode": False,
    "branch_spacing": 3,  # Відстань між гілками за замовчуванням
    "overlap": "true"
}

# Функція для оновлення глобальних налаштувань
def update_global_settings(new_settings):
    global global_settings
    global_settings.update(new_settings)

# Попередня обробка C-коду
def preprocess_code(c_code):
    import re
    # Видалення коментарів типу //
    c_code = re.sub(r'//.*?$', '', c_code, flags=re.MULTILINE)
    # Видалення коментарів типу /* */
    c_code = re.sub(r'/\*.*?\*/', '', c_code, flags=re.DOTALL)
    # Видалення директив препроцесора
    c_code = "\n".join(line for line in c_code.splitlines() if not line.strip().startswith("#"))
    # Видалення директив using
    c_code = "\n".join(line for line in c_code.splitlines() if not line.strip().startswith("using"))
    return c_code

# Генерація блок-схеми
def generate_flowchart(c_code):
    import os
    import requests
    import textwrap
    from graphviz import Digraph
    from pycparser import c_parser, c_ast

    # Створення тимчасового каталогу для збереження файлів
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Попередня обробка C-коду
    c_code = preprocess_code(c_code)
    
    # Парсинг C-коду
    parser = c_parser.CParser()
    ast = parser.parse(c_code)

    # Збереження AST у файл для подальшого використання
    ast_file_path = os.path.join(temp_dir, 'ast.txt')
    with open(ast_file_path, 'w') as ast_file:
        ast_file.write(str(ast))

    # Створення об'єкту блок-схеми
    dot = Digraph(engine='fdp')
    dot.attr(overlap='vpsc')  # Налаштування для уникнення накладання блоків

    if global_settings["online_mode"]:
        dot.body.append('layout=fdp')  # Вказівка для використання онлайн-режиму

    node_counter = 0
    y_position = 0
    max_depth_y = y_position
    function_names = set()
    
    # Витягнення імен функцій з AST
    for ext in ast.ext:
        if isinstance(ext, c_ast.FuncDef):
            function_names.add(ext.decl.name)

    # Функція для додавання блоку до блок-схеми
    def add_node(label, shape='rectangle', width=None, height=None, cluster=None, fontsize=None, pos=None, x=12):
        nonlocal node_counter, y_position, max_depth_y
        width = width or global_settings["node_width"]
        height = height or global_settings["node_height"]
        fontsize = fontsize or global_settings["node_fontsize"]
        wrapped_label = wrap_label(label)
        node_id = f"node{node_counter}"
        node_attrs = {
            'shape': shape,
            'fontsize': str(fontsize),
            'width': str(width),
            'height': str(height),
            'fixedsize': 'true',
            'penwidth': str(global_settings["node_penwidth"]),
            'pin': 'true',
            'pos': pos if pos else f"{x},{y_position}!"
        }
        if shape == 'point':
            node_attrs.update({
                'width': '0',
                'height': '0',
                'style': 'invis'
            })
        if not pos:
            y_position -= 1.5
        if y_position < max_depth_y:
            max_depth_y = y_position
        if cluster:
            cluster.node(node_id, wrapped_label, **node_attrs)
        else:
            dot.node(node_id, wrapped_label, **node_attrs)
        node_counter += 1
        return node_id

    # Функція для додавання спеціального блоку (для особливих форм)
    def add_special_node(label, shape, cluster=None, fontsize=None, x=12):
        return add_node(label, shape=shape, width=global_settings["special_shape_width"], height=global_settings["node_height"], cluster=cluster, fontsize=fontsize, x=x)

    # Функція для очищення мітки блоку
    def clean_label(label):
        label = label.strip()
        if label.endswith(";"):
            label = label[:-1]
        if label.endswith("{"):
            label = label[:-1]
        return label.strip()

    # Функція для переносу тексту в тексті блоку
    def wrap_label(label):
        width_factor = global_settings["width_factor"]
        return r"\n".join(textwrap.wrap(label, width_factor))

    # Функція для отримання рядка коду за координатами
    def get_code_line(node):
        return clean_label(c_code.split('\n')[node.coord.line - 1])

    # Функція для форматування умовних виразів
    def format_cond(cond):
        if isinstance(cond, c_ast.BinaryOp):
            left = format_cond(cond.left)
            right = format_cond(cond.right)
            return f"({left} {cond.op} {right})"
        elif isinstance(cond, c_ast.ID):
            return cond.name
        elif isinstance(cond, c_ast.Constant):
            return cond.value
        elif isinstance(cond, c_ast.ArrayRef):
            return f"{format_cond(cond.name)}[{format_cond(cond.subscript)}]"
        else:
            return str(cond)

    # Функція для збереження пробілів в тексті
    def preserve_spaces(text):
        return text.replace(" ", "&nbsp;")

    # Обробка циклу for
    def handle_for_loop(node, parent_id, cluster, edge_label=None, tailport='s', headport='n', depth=0):
        nonlocal y_position
        label = get_code_line(node)
        for_node_id = add_special_node(label, shape='hexagon', cluster=cluster, x=12)
        loop_start_y = y_position
        if parent_id:
            cluster.edge(f"{parent_id}:{tailport}", f"{for_node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
        
        body_id, body_tailport = traverse_ast(node.stmt, for_node_id, cluster, tailport='s', headport='n', depth=depth + 1)

        x_position_inner = 12 - (depth + 0.5)
        x_position_outer = x_position_inner - 1.5
        if depth > 0:
            x_position = x_position_inner
        else:
            x_position = x_position_outer

        bend_point_below_y = y_position
        bend_point_below_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12 )
        bend_point_left_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_inner, pos=f"{x_position},{bend_point_below_y}!")
        bend_point_above_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_inner, pos=f"{x_position},{loop_start_y + 1.5}!")

        x_position_inner_right = 12 + (depth + 0.5)
        x_position_outer_right = x_position_inner_right + 1.5
        if depth > 0:
            x_position_right = x_position_inner_right
        else:
            x_position_right = x_position_outer_right

        bend_point_right_x = x_position_right
        bend_point_right_y = loop_start_y + 1.5
        bend_point_right_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=bend_point_right_x, pos=f"{bend_point_right_x},{bend_point_right_y}!")

        if depth > 0:
            intermediate_node_x = bend_point_right_x
            intermediate_node_y = bend_point_below_y - 1.5
            intermediate_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=intermediate_node_x, pos=f"{intermediate_node_x},{intermediate_node_y}!")

        if depth == 0:
            additional_node_y = bend_point_below_y - 0.75
            left_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{additional_node_y}!")
            additional_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=bend_point_right_x, pos=f"{bend_point_right_x},{additional_node_y}!")

        cluster.edge(f"{body_id}:{body_tailport}", f"{bend_point_below_id}:", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_below_id}:w", f"{bend_point_left_id}:e", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_left_id}:n", f"{bend_point_above_id}:s", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_above_id}:e", f"{for_node_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["loopback_arrows"])
        cluster.edge(f"{for_node_id}:e", f"{bend_point_right_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        if depth == 0:
            cluster.edge(f"{bend_point_right_id}:s", f"{additional_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            cluster.edge(f"{additional_node_id}:w", f"{left_node_id}:e", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            return left_node_id, 's'
        else:
            cluster.edge(f"{bend_point_right_id}:s", f"{intermediate_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            return intermediate_node_id, 'e'

    # Обробка циклу while
    def handle_while_loop(node, parent_id, cluster, edge_label=None, tailport='s', headport='n', depth=0):
        nonlocal y_position
        label = get_code_line(node)
        while_node_id = add_special_node(label, shape='diamond', cluster=cluster, x=12)
        loop_start_y = y_position
        if parent_id:
            cluster.edge(f"{parent_id}:{tailport}", f"{while_node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
        
        body_id, body_tailport = traverse_ast(node.stmt, while_node_id, cluster, tailport='s', headport='n', depth=depth + 1)

        x_position_inner = 12 - (depth + 0.5)
        x_position_outer = x_position_inner - 1.5
        if depth > 0:
            x_position = x_position_inner
        else:
            x_position = x_position_outer

        bend_point_below_y = y_position
        bend_point_below_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12)
        bend_point_left_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_inner, pos=f"{x_position},{bend_point_below_y}!")
        bend_point_above_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_inner, pos=f"{x_position},{loop_start_y + 1.5}!")

        x_position_inner_right = 12 + (depth + 0.5)
        x_position_outer_right = x_position_inner_right + 1.5
        if depth > 0:
            x_position_right = x_position_inner_right
        else:
            x_position_right = x_position_outer_right

        bend_point_right_x = x_position_right
        bend_point_right_y = loop_start_y + 1.5
        bend_point_right_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=bend_point_right_x, pos=f"{bend_point_right_x},{bend_point_right_y}!")

        if depth > 0:
            intermediate_node_x = bend_point_right_x
            intermediate_node_y = bend_point_below_y - 1.5
            intermediate_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=intermediate_node_x, pos=f"{intermediate_node_x},{intermediate_node_y}!")

        if depth == 0:
            additional_node_y = bend_point_below_y - 0.75
            left_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{additional_node_y}!")
            additional_node_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=bend_point_right_x, pos=f"{bend_point_right_x},{additional_node_y}!")

        cluster.edge(f"{body_id}:{body_tailport}", f"{bend_point_below_id}:", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_below_id}:w", f"{bend_point_left_id}:e", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_left_id}:n", f"{bend_point_above_id}:s", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{bend_point_above_id}:e", f"{while_node_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["loopback_arrows"])
        cluster.edge(f"{while_node_id}:e", f"{bend_point_right_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        if depth == 0:
            cluster.edge(f"{bend_point_right_id}:s", f"{additional_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            cluster.edge(f"{additional_node_id}:w", f"{left_node_id}:e", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            return left_node_id, 's'
        else:
            cluster.edge(f"{bend_point_right_id}:s", f"{intermediate_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
            return intermediate_node_id, 'e'

    # Обробка оператора switch
    def handle_switch_case(node, parent_id, cluster, edge_label=None, tailport='s', headport='n', depth=0):
        nonlocal y_position, node_counter
        switch_label = get_code_line(node)
        switch_node_id = add_node(switch_label, shape='box', cluster=cluster, x=12)
        if parent_id:
            cluster.edge(f"{parent_id}:{tailport}", f"{switch_node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])

        num_cases = len(node.stmt.block_items)
        base_x = 12 - ((num_cases - 1) * global_settings["branch_spacing"]) / 2
        case_x_positions = [base_x + i * global_settings["branch_spacing"] for i in range(num_cases)]
        case_y_position = y_position
        max_y_positions = []
        case_concentrators = []

        previous_case_id = None
        for i, case in enumerate(node.stmt.block_items):
            if isinstance(case, c_ast.Case):
                case_label = f"case {format_cond(case.expr)}:"
                case_node_id = add_node(case_label, shape='diamond', cluster=cluster, x=case_x_positions[i], pos=f"{case_x_positions[i]},{case_y_position}!")
                if previous_case_id is None:
                    switch_case_y = case_y_position + 0.75
                    switch_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{switch_case_y}!")
                    case_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=case_x_positions[i], pos=f"{case_x_positions[i]},{switch_case_y}!")
                    cluster.edge(f"{switch_node_id}:s", f"{switch_point_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
                    cluster.edge(f"{switch_point_id}:e", f"{case_point_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
                    cluster.edge(f"{case_point_id}:s", f"{case_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                else:
                    cluster.edge(f"{previous_case_id}:e", f"{case_node_id}:w", label="false", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                previous_case_id = case_node_id

                content_y_position = case_y_position - 1.5
                last_stmt_id = case_node_id
                for stmt in case.stmts:
                    stmt_id, stmt_tailport = traverse_ast(stmt, last_stmt_id, cluster, edge_label="true", depth=depth + 1, x=case_x_positions[i], y_pos=content_y_position)
                    content_y_position -= 1.5
                    last_stmt_id = stmt_id
                max_y_positions.append(content_y_position)
                case_concentrators.append((case_node_id, last_stmt_id))
            elif isinstance(case, c_ast.Default):
                default_label = "default:"
                default_node_id = add_node(default_label, shape='diamond', cluster=cluster, x=case_x_positions[i], pos=f"{case_x_positions[i]},{case_y_position}!")
                if previous_case_id is None:
                    switch_case_y = case_y_position + 0.75
                    switch_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{switch_case_y}!")
                    case_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=case_x_positions[i], pos=f"{case_x_positions[i]},{switch_case_y}!")
                    cluster.edge(f"{switch_node_id}:s", f"{switch_point_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
                    cluster.edge(f"{switch_point_id}:e", f"{case_point_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
                    cluster.edge(f"{case_point_id}:s", f"{default_node_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                else:
                    cluster.edge(f"{previous_case_id}:e", f"{default_node_id}:w", label="false", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                previous_case_id = default_node_id

                content_y_position = case_y_position - 1.5
                last_stmt_id = default_node_id
                for stmt in case.stmts:
                    stmt_id, stmt_tailport = traverse_ast(stmt, last_stmt_id, cluster, edge_label="true", depth=depth + 1, x=case_x_positions[i], y_pos=content_y_position)
                    content_y_position -= 1.5
                    last_stmt_id = stmt_id
                max_y_positions.append(content_y_position)
                case_concentrators.append((default_node_id, last_stmt_id))

        min_y_position = min(max_y_positions) if max_y_positions else case_y_position - 1.5

        y_concentrator = min_y_position + 0.75
        concentrator_ids = []
        for case_node_id, last_stmt_id in case_concentrators:
            concentrator_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=case_x_positions[case_concentrators.index((case_node_id, last_stmt_id))], pos=f"{case_x_positions[case_concentrators.index((case_node_id, last_stmt_id))]},{y_concentrator}!")
            concentrator_ids.append(concentrator_id)
            cluster.edge(f"{last_stmt_id}:{tailport}", f"{concentrator_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])

        if len(concentrator_ids) > 1:
            cluster.edge(f"{concentrator_ids[0]}:e", f"{concentrator_ids[-1]}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        additional_concentrator_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{y_concentrator}!")
        if len(concentrator_ids) > 0:
            cluster.edge(f"{concentrator_ids[-1]}:e", f"{additional_concentrator_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        return additional_concentrator_id, 's'

    # Обробка одногілкового оператора if
    def handle_single_branch_if(node, parent_id, cluster, edge_label=None, tailport='s', headport='n', depth=0, x=12):
        nonlocal y_position
        label = f"if {format_cond(node.cond)}"
        if_node_id = add_special_node(label, shape='diamond', cluster=cluster, x=x)
        if parent_id:
            cluster.edge(f"{parent_id}:{tailport}", f"{if_node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])

        true_branch_x = x
        current_y = y_position

        y_position = current_y
        true_branch_id, true_tailport = traverse_ast(node.iftrue, if_node_id, cluster, edge_label="True", tailport='s', headport='n', depth=depth + 1, x=true_branch_x)

        x_position_inner = x + 1.3
        x_position_outer = x_position_inner
        
        if depth > 0:
            x_position=x_position_inner
        else:
            x_position=x_position_outer

        true_bend_point1_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_outer, pos=f"{x_position},{current_y + 1.5}!")
        true_bend_point2_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x_position_outer, pos=f"{x_position},{current_y - 0.75}!")

        last_true_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=x, pos=f"{x},{current_y - 0.75}!")

        cluster.edge(f"{if_node_id}:e", f"{true_bend_point1_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{true_bend_point1_id}:s", f"{true_bend_point2_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{true_bend_point2_id}:e", f"{last_true_point_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])

        return true_branch_id, 's'

    # Обробка двогілкового оператора if-else
    def handle_if_else(node, parent_id, cluster, edge_label=None, tailport='s', headport='n', depth=0, x=12):
        nonlocal y_position
        label = f"if {format_cond(node.cond)}"
        if_node_id = add_special_node(label, shape='diamond', cluster=cluster, x=x)
        if parent_id:
            cluster.edge(f"{parent_id}:{tailport}", f"{if_node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])

        branch_spacing = global_settings["branch_spacing"] / (depth + 1)
        true_branch_x = x - branch_spacing
        false_branch_x = x + branch_spacing
        current_y = y_position

        true_bend_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=true_branch_x, pos=f"{true_branch_x},{current_y + 1.5}!")
        false_bend_point_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=false_branch_x, pos=f"{false_branch_x},{current_y + 1.5}!")

        cluster.edge(f"{if_node_id}:w", f"{true_bend_point_id}:e", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{if_node_id}:e", f"{false_bend_point_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        y_position = current_y
        true_branch_id, true_tailport = traverse_ast(node.iftrue, true_bend_point_id, cluster, edge_label="True", tailport='s', headport='n', depth=depth + 1, x=true_branch_x)

        y_position = current_y
        false_branch_id, false_tailport = traverse_ast(node.iffalse, false_bend_point_id, cluster, edge_label="False", tailport='s', headport='n', depth=depth + 1, x=false_branch_x)

        concentrator_y = min(y_position, current_y) + 0.75

        true_concentrator_id, false_concentrator_id = None, None

        if not isinstance(node.iftrue, c_ast.If):
            true_concentrator_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=true_branch_x, pos=f"{true_branch_x},{concentrator_y}!")
            cluster.edge(f"{true_branch_id}:{true_tailport}", f"{true_concentrator_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
        else:
            true_concentrator_id = true_branch_id

        if not isinstance(node.iffalse, c_ast.If):
            false_concentrator_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=false_branch_x, pos=f"{false_branch_x},{concentrator_y}!")
            cluster.edge(f"{false_branch_id}:{false_tailport}", f"{false_concentrator_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
        else:
            false_concentrator_id = false_branch_id

        if true_concentrator_id and false_concentrator_id:
            cluster.edge(f"{true_concentrator_id}:e", f"{false_concentrator_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        additional_concentrator_id = add_node("", shape='point', width=0.1, height=0.1, cluster=cluster, x=12, pos=f"12,{concentrator_y}!")
        cluster.edge(f"{true_concentrator_id}:e", f"{additional_concentrator_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')
        cluster.edge(f"{false_concentrator_id}:w", f"{additional_concentrator_id}:w", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead='none')

        return additional_concentrator_id, 's'

    # Функція для проходження AST (Abstract Syntax Tree) та генерації блок-схеми
    def traverse_ast(node, parent_id=None, cluster=None, edge_label=None, tailport='s', headport='n', depth=0, x=12, y_pos=None):
        nonlocal node_counter, y_position, max_depth_y
        if y_pos is not None:
            y_position = y_pos

        decl_nodes = []

        if isinstance(node, c_ast.Compound):
            for stmt in node.block_items:
                if isinstance(stmt, c_ast.Decl):
                    decl_nodes.append(stmt)
                else:
                    if decl_nodes:
                        combined_label = ", ".join(get_code_line(decl) for decl in decl_nodes)
                        node_id = add_node(combined_label, cluster=cluster, x=x)
                        if parent_id:
                            cluster.edge(f"{parent_id}:{tailport}", f"{node_id}:{headport}", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                        parent_id = node_id
                        tailport = 's'
                        decl_nodes.clear()
                    parent_id, tailport = traverse_ast(stmt, parent_id, cluster, edge_label, tailport, headport, depth, x)
            if decl_nodes:
                combined_label = ", ".join(get_code_line(decl) for decl in decl_nodes)
                node_id = add_node(combined_label, cluster=cluster, x=x)
                if parent_id:
                    cluster.edge(f"{parent_id}:{tailport}", f"{node_id}:{headport}", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
                parent_id = node_id
                tailport = 's'
            return parent_id, tailport
        elif isinstance(node, (c_ast.Assignment, c_ast.Return)):
            label = get_code_line(node)
            if label == "return 0":
                return parent_id, tailport
            shape = 'rectangle'
            width = global_settings["node_width"]
            if any(func_name in label for func_name in function_names):
                label = f"| {wrap_label(label)} |"  # Перенос тексту для користувацьких функцій
                shape = 'record'
                width = global_settings["special_shape_width"]
            node_id = add_node(label, shape=shape, width=width, cluster=cluster, x=x)
            if parent_id:
                cluster.edge(f"{parent_id}:{tailport}", f"{node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
            return node_id, 's'
        elif isinstance(node, c_ast.FuncCall):
            func_name = node.name.name
            label = get_code_line(node)
            shape = 'rectangle'
            width = global_settings["node_width"]
            if func_name == "printf":
                label = f"Вивести: {label[label.index('(') + 1:label.rindex(')')]}"
                shape = 'parallelogram'
                width = global_settings["special_shape_width"]
            elif func_name == "scanf":
                label = f"Ввести: {label[label.index('(') + 1:label.rindex(')')]}"
                shape = 'parallelogram'
                width = global_settings["special_shape_width"]
            elif func_name in function_names:
                label = f"| {wrap_label(label)} |"  # Перенос тексту для користувацьких функцій
                shape = 'record'
                width = global_settings["special_shape_width"]
            node_id = add_node(label, shape=shape, width=width, cluster=cluster, x=x)
            if parent_id:
                cluster.edge(f"{parent_id}:{tailport}", f"{node_id}:{headport}", label=edge_label, fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
            return node_id, 's'
        elif isinstance(node, c_ast.If):
            false_branch = node.iffalse
            if isinstance(false_branch, c_ast.Compound) and len(false_branch.block_items) == 1 and isinstance(false_branch.block_items[0], c_ast.Continue):
                false_branch = None
            if false_branch:
                return handle_if_else(node, parent_id, cluster, edge_label, tailport, headport, depth, x)
            else:
                return handle_single_branch_if(node, parent_id, cluster, edge_label, tailport, headport, depth, x)
        elif isinstance(node, c_ast.For):
            return handle_for_loop(node, parent_id, cluster, edge_label, tailport, headport, depth)
        elif isinstance(node, c_ast.While):
            return handle_while_loop(node, parent_id, cluster, edge_label, tailport, headport, depth)
        elif isinstance(node, c_ast.Switch):
            return handle_switch_case(node, parent_id, cluster, edge_label, tailport, headport, depth)

        return parent_id, tailport

    cluster_ids = []

    # Генерація блок-схем для кожної функції
    for ext in ast.ext:
        if isinstance(ext, c_ast.FuncDef):
            func_decl = get_code_line(ext.decl)
            func_decl = preserve_spaces(func_decl)
            with dot.subgraph(name=f'cluster_{ext.decl.name}') as cluster:
                cluster.attr(label=f"< <B>Блок-схема для функції {func_decl}</B> >", labelloc="t", fontsize=str(global_settings["cluster_fontsize"]), margin=str(global_settings["cluster_margin"]))
                cluster.attr(overlap='true')
                start_id = add_node('Start', shape='Mrecord', height=global_settings["start_end_height"], cluster=cluster, pos=f"12,{y_position}!")
                y_position -= 1.5
                max_depth_y = y_position
                parent_id, tailport = traverse_ast(ext.body, start_id, cluster, depth=0, x=12)
                end_id = add_node('End', shape='Mrecord', height=global_settings["start_end_height"], cluster=cluster, pos=f"12,{max_depth_y}!")
                y_position = max_depth_y
                cluster.edge(f"{parent_id}:{tailport}", f"{end_id}:n", fontsize=str(global_settings["edge_fontsize"]), penwidth=str(global_settings["edge_penwidth"]), arrowhead=global_settings["edge_arrows"])
            cluster_ids.append(f'cluster_{ext.decl.name}')

    # З'єднання кластерів невидимими з'єднаннями, для запобігання розкидання по полотну
    for i in range(len(cluster_ids) - 1):
        dot.edge(cluster_ids[i], cluster_ids[i + 1], style='invis', len='0.1')

    dot_output = dot.source

    dot_file_path = os.path.join(temp_dir, 'flowchart.dot')
    with open(dot_file_path, 'w') as dot_file:
        dot_file.write(dot_output)

    if global_settings["online_mode"]:
        url = "https://kroki.io/graphviz/svg"
        headers = {
            "Content-Type": "text/plain"
        }
        response = requests.post(url, headers=headers, data=dot_output.encode("utf-8"))

        if response.status_code == 200:
            svg_output = response.content
            svg_file_path = os.path.join(temp_dir, 'flowchart.svg')
            with open(svg_file_path, 'wb') as svg_file:
                svg_file.write(svg_output)
            return dot_output, svg_file_path
        else:
            raise Exception(f"Error generating flowchart: {response.status_code} {response.text}")
    else:
        dot_path = os.path.join(temp_dir, 'flowchart')
        dot.render(dot_path, format='svg')
        return dot_output, f"{dot_path}.svg"

# Основна функція для запуску генерації блок-схеми
def main():
    new_settings = {
        "online_mode": False
    }
    update_global_settings(new_settings)

    example_c_code = """
    int main() {
        int a = 10;
        if (a > 5) {
            a = 5;
        }
        return 0;
    }
    """

    dot_output, svg_path = generate_flowchart(example_c_code)

    print(dot_output)
    print(f"Flowchart SVG file saved at: {svg_path}")

if __name__ == "__main__":
    main()
