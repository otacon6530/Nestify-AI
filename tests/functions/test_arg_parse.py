from nestify_core.functions.arg_parse import parse

def test_parse_exec():
    args = parse(["exec", "hello"])
    assert args["command"] == "exec"
    assert args["message"] == "hello"

def test_parse_run():
    args = parse(["run"])  
    assert args["command"] == "run"

def test_parse_shell():
    args = parse(["shell", "echo hi"])  
    assert args["command"] == "shell"
    assert args["shell_command"] == "echo hi"
