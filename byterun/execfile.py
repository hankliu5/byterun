"""Execute files of Python code."""

import imp
import os
import sys
import tokenize
import types
import importlib
from .flow_analysis import flow_analysis, get_import_name
from .pyvm2 import VirtualMachine, VirtualMachinePause, VirtualMachineError


# This code is ripped off from coverage.py.  Define things it expects.
try:
    open_source = tokenize.open     # pylint: disable=E1101
except:
    def open_source(fname):
        """Open a source file the best way."""
        return open(fname, "rU")

NoSource = Exception


def first(s):
    """Return the first element from an ordered collection
       or an arbitrary element from an unordered collection.
       Raise StopIteration if the collection is empty.
    """
    return next(iter(s))


def exec_code_object(code, env):
    pause_time = 0

    # do the code analysis to get the variables that are necessary to send before finishing each line
    # and the lines of import libraries
    var_to_send_ordered_dict, import_lib_arr = flow_analysis(code)
    import_lib_names_arr = get_import_name(import_lib_arr)

    # import the libraries outside the VM because for different VM, the path might be different
    # So, need to import again when we migrate to the other environment
    for lib_name in import_lib_names_arr:
        env[lib_name] = importlib.import_module(lib_name)

    # Store the original env dictionary
    original_env = env.copy()

    # start from the first execution line after import part
    first_execution_line = first(var_to_send_ordered_dict)
    vm = VirtualMachine()
    vm.var_to_send_ordered_dict = var_to_send_ordered_dict
    try:
        vm.run_code(code, f_globals=env, first_execution_line=first_execution_line)
    except VirtualMachinePause:
        pause_time += 1
        while True:
            try:
                # simulate the migration step
                new_vm = VirtualMachine()
                new_vm.var_to_send_ordered_dict = var_to_send_ordered_dict

                # The pause is right before the execution of the instruction
                # so we need to rewind back to the starting instruction of the current line
                current_line_no = vm.offset_line_dict[vm.last_line_offset]
                var_to_send_at_this_line = var_to_send_ordered_dict[current_line_no]
                print("I'm on line {}".format(current_line_no))
                print("Variables to send are {}\n".format(var_to_send_at_this_line))

                # put the necessary variables to the new env dictionary for migration
                new_env = original_env.copy()
                for var_name in var_to_send_at_this_line:
                    new_env[var_name] = vm.frame.f_locals[var_name]

                # new VM setup
                new_vm.frame = new_vm.make_frame(code, f_globals=new_env)
                new_vm.last_line_offset = vm.last_line_offset
                new_vm.offset_line_dict = vm.offset_line_dict
                new_vm.frame.f_lasti = vm.last_line_offset
                new_vm.start_time = vm.start_time
                new_vm.code_time_map = vm.code_time_map
                new_vm.code_size_map = vm.code_size_map

                # drop the old VM and resume the frame
                del vm
                vm = new_vm
                vm.resume_frame(vm.frame)
            except VirtualMachinePause:
                pause_time += 1
                continue
            break

    if vm.frames:  # pragma: no cover
        raise VirtualMachineError("Frames left over!")
    if vm.frame and vm.frame.stack:  # pragma: no cover
        raise VirtualMachineError("Data left on stack! %r" % vm.frame.stack)
    print(vm.code_time_map)
    print(var_to_send_ordered_dict)
    print(vm.code_size_map)
    print('pause time: {}'.format(pause_time))

# from coverage.py:

try:
    # In Py 2.x, the builtins were in __builtin__
    BUILTINS = sys.modules['__builtin__']
except KeyError:
    # In Py 3.x, they're in builtins
    BUILTINS = sys.modules['builtins']


def rsplit1(s, sep):
    """The same as s.rsplit(sep, 1), but works in 2.3"""
    parts = s.split(sep)
    return sep.join(parts[:-1]), parts[-1]


def run_python_module(modulename, args):
    """Run a python module, as though with ``python -m name args...``.

    `modulename` is the name of the module, possibly a dot-separated name.
    `args` is the argument array to present as sys.argv, including the first
    element naming the module being executed.

    """
    openfile = None
    glo, loc = globals(), locals()
    try:
        try:
            # Search for the module - inside its parent package, if any - using
            # standard import mechanics.
            if '.' in modulename:
                packagename, name = rsplit1(modulename, '.')
                package = __import__(packagename, glo, loc, ['__path__'])
                searchpath = package.__path__
            else:
                packagename, name = None, modulename
                searchpath = None  # "top-level search" in imp.find_module()
            openfile, pathname, _ = imp.find_module(name, searchpath)

            # Complain if this is a magic non-file module.
            if openfile is None and pathname is None:
                raise NoSource(
                    "module does not live in a file: %r" % modulename
                    )

            # If `modulename` is actually a package, not a mere module, then we
            # pretend to be Python 2.7 and try running its __main__.py script.
            if openfile is None:
                packagename = modulename
                name = '__main__'
                package = __import__(packagename, glo, loc, ['__path__'])
                searchpath = package.__path__
                openfile, pathname, _ = imp.find_module(name, searchpath)
        except ImportError:
            _, err, _ = sys.exc_info()
            raise NoSource(str(err))
    finally:
        if openfile:
            openfile.close()

    # Finally, hand the file off to run_python_file for execution.
    args[0] = pathname
    run_python_file(pathname, args, package=packagename)


def run_python_file(filename, args, package=None):
    """Run a python file as if it were the main program on the command line.

    `filename` is the path to the file to execute, it need not be a .py file.
    `args` is the argument array to present as sys.argv, including the first
    element naming the file being executed.  `package` is the name of the
    enclosing package, if any.

    """
    # Create a module to serve as __main__
    old_main_mod = sys.modules['__main__']
    main_mod = types.ModuleType('__main__')
    sys.modules['__main__'] = main_mod
    main_mod.__file__ = filename
    if package:
        main_mod.__package__ = package
    main_mod.__builtins__ = BUILTINS

    # Set sys.argv and the first path element properly.
    old_argv = sys.argv
    old_path0 = sys.path[0]
    sys.argv = args
    if package:
        sys.path[0] = ''
    else:
        sys.path[0] = os.path.abspath(os.path.dirname(filename))

    try:
        # Open the source file.
        try:
            source_file = open_source(filename)
        except IOError:
            raise NoSource("No file to run: %r" % filename)

        try:
            source = source_file.read()
        finally:
            source_file.close()

        # We have the source.  `compile` still needs the last line to be clean,
        # so make sure it is, then compile a code object from it.
        if not source or source[-1] != '\n':
            source += '\n'
        code = compile(source, filename, "exec")

        # Execute the source file.
        exec_code_object(code, main_mod.__dict__)
    finally:
        # Restore the old __main__
        sys.modules['__main__'] = old_main_mod

        # Restore the old argv and path
        sys.argv = old_argv
        sys.path[0] = old_path0
