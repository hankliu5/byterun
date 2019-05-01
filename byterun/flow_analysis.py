import dis
import sys
from collections import OrderedDict


def get_import_name(import_lib_arr):
    import_names = []
    for line in import_lib_arr:
        for i in line:
            if i.opname.startswith('IMPORT_'):
                import_names.append(i.argval)
                break
    return import_names


def flow_analysis(c):
    # dissemble bytecode to a Bytecode object to examine
    bytecode = dis.Bytecode(c)
    line_blocks = []
    tmp = []

    # Reorganize instructions based on lines
    for i in bytecode:
        if i.starts_line and len(tmp) > 0:
            line_blocks.append(tmp)
            tmp = []
        tmp.append(i)
    line_blocks.append(tmp)

    # Ignore import line
    new_line_blocks = []
    import_lib_arr = []
    for line in line_blocks:
        import_line = False
        for i in line:
            if i.opname.startswith('IMPORT_'):
                import_lib_arr.append(line)
                import_line = True
                break
        if not import_line:
            new_line_blocks.append(line)

    line_blocks = new_line_blocks

    # Get the user-defined variables for each line in the script
    available_customized_vars_ordered_dict = OrderedDict()
    customized_vars = set()
    for line in line_blocks:
        available_customized_vars_ordered_dict[line[0].starts_line] = customized_vars.copy()
        for i in line:
            if i.opname.startswith('STORE_'):
                customized_vars.add(i.argval)
    available_customized_vars_ordered_dict[line_blocks[-1][0].starts_line + 1] = set()

    # Calculate UEVar and VarKill for each line
    line_livein_ordered_dict = OrderedDict()
    line_varkill_ordered_dict = OrderedDict()

    for line in line_blocks:
        livein = set()
        VarKill = set()
        for i in line:
            if i.opname.startswith('LOAD_NAME') and i.argval in customized_vars:
                livein.add(i.argval)
            if i.opname.startswith('STORE_NAME') and i.argval in customized_vars:
                VarKill.add(i.argval)

        line_livein_ordered_dict[line[0].starts_line] = livein
        line_varkill_ordered_dict[line[0].starts_line] = VarKill

    # Calculate the liveout variable for each line
    line_liveout_ordered_dict = OrderedDict()
    for line in line_blocks:
        line_liveout_ordered_dict[line[0].starts_line] = set()

    change = True
    while change:
        change = False
        for i, line in enumerate(line_blocks):
            new_liveout = set()
            for successor_line in line_blocks[i:]:
                successor_line_number = successor_line[0].starts_line
                new_liveout = new_liveout | (line_livein_ordered_dict[successor_line_number] | (line_liveout_ordered_dict[successor_line_number] & (customized_vars - line_varkill_ordered_dict[successor_line_number])))
            if new_liveout != line_liveout_ordered_dict[line[0].starts_line]:
                change = True
                line_liveout_ordered_dict[line[0].starts_line] = new_liveout

    line_liveout_ordered_dict[line_blocks[-1][0].starts_line+1] = set()

    # Get the variables that are necessary to send for each line
    var_to_send_ordered_dict = OrderedDict()
    for line_number, liveout in line_liveout_ordered_dict.items():
        available = available_customized_vars_ordered_dict[line_number]
        var_to_send_ordered_dict[line_number] = (liveout & available)

    return var_to_send_ordered_dict, import_lib_arr


if __name__ == '__main__':
    filename = sys.argv[1]

    # compile python script to bytecode
    with open(filename, 'r') as f:
        co = compile(f.read(), filename, 'exec')

    var_to_send_ordered_dict, import_lib_arr = flow_analysis(co)

    print(var_to_send_ordered_dict)
    print(import_lib_arr)
