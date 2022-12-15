def save_file(content, file_path):
    if file_path.exists():
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
