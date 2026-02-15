- pip install dist/ztc-0.1.0-py3-none-any.whl --force-reinstall --no-deps 2>&1 | tail -10
- pip install dist/ztc-0.1.0-py3-none-any.whl --force-reinstall 2>&1 | tail -5
- ztc version
- poetry run pyinstaller ztc.spec --clean 2>&1 | tail -50
- ./dist/ztc --help
- ./dist/ztc version

