class ErrorStats:
    missing_rr = "missing_rename_refactoring"
    missing_chn = "missing_covered_changes"
    missing_cg = "missing_call_graph"
    missing_te = "missing_test_elements"
    __stats = {
        missing_rr: set(),
        missing_chn: set(),
        missing_cg: set(),
        missing_te: set(),
    }

    @staticmethod
    def update(name, value):
        if name in ErrorStats.__stats:
            ErrorStats.__stats[name].add(value)

    @staticmethod
    def report():
        if all([(len(values) == 0) for _, values in ErrorStats.__stats.items()]):
            return
        print("\n\n-- Error Stats --")
        for err, values in ErrorStats.__stats.items():
            print(f"    {err} had {len(values)} errors -> {list(values)}")
