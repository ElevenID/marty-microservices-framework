try:
    import mmf.security.unified_framework

    print("Found mmf.security.unified_framework")
except ImportError:
    print("Not found mmf.security.unified_framework")

try:
    import marty_msf.security.unified_framework

    print("Found marty_msf.security.unified_framework")
except ImportError:
    print("Not found marty_msf.security.unified_framework")
