def read_lines(file):
    with open(file) as f:
        return [line.rstrip() for line in f]


def write_lines(file, lines):
    with open(file, "w") as f:
        f.write("\n".join(lines))
        f.write("\n")