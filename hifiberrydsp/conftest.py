
def pytest_configure(config):
    import hifiberrydsp
    hifiberrydsp._called_from_test = True