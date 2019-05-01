import dis
import sys


def get_var_to_send(c):
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
    for line in line_blocks:
        import_line = False
        for i in line:
            if i.opname.startswith('IMPORT_'):
                import_line = True
                break
        if not import_line:
            new_line_blocks.append(line)

    line_blocks = new_line_blocks

    # Get the user-defined variables for each line in the script
    available_customized_vars = [set()]
    customized_vars = set()
    for line in line_blocks:
        for i in line:
            if i.opname.startswith('STORE_'):
                customized_vars.add(i.argval)
        available_customized_vars.append(customized_vars.copy())

    # Calculate UEVar and VarKill for each line
    line_livein_arr = []
    line_varkill_arr = []

    for line in line_blocks:
        livein = set()
        VarKill = set()
        for i in line:
            if i.opname.startswith('LOAD_NAME') and i.argval in customized_vars:
                livein.add(i.argval)
            if i.opname.startswith('STORE_NAME') and i.argval in customized_vars:
                VarKill.add(i.argval)

        line_livein_arr.append(livein)
        line_varkill_arr.append(VarKill)

    # Calculate the liveout variable for each line
    line_liveout_arr = [set() for _ in range(len(line_blocks))]
    change = True
    while change:
        change = False
        for i in range(len(line_blocks)):
            new_liveout = set()
            for j in range(i, len(line_blocks)):
                new_liveout = new_liveout | (line_livein_arr[j] | (line_liveout_arr[j] & (customized_vars - line_varkill_arr[j])))
            if new_liveout != line_liveout_arr[i]:
                change = True
                line_liveout_arr[i] = new_liveout
    line_liveout_arr.append(set())

    # Get the variables that are necessary to send for each line
    var_to_send_arr = []
    for liveout, available in zip(line_liveout_arr, available_customized_vars):
        var_to_send_arr.append(liveout & available)

    return var_to_send_arr


if __name__ == '__main__':
    filename = sys.argv[1]

    # compile python script to bytecode
    with open(filename, 'r') as f:
        co = compile(f.read(), filename, 'exec')

    print(get_var_to_send(co))
