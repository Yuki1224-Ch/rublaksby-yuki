import os

# combocheck.py
class ComboCheck:
    def __init__(self, filepath=None):
        self._filepath = filepath
        self._content = ""
        if filepath:
            self.read_file(filepath)
    
    def read_file(self, path):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self._content = f.read()
    
    def contains(self, s):
        return s in self._content
    
    def append(self, s):
        self._content += s
        # Also write to file if filepath is set
        if self._filepath:
            os.makedirs(os.path.dirname(self._filepath) or ".", exist_ok=True)
            with open(self._filepath, "a", encoding="utf-8") as f:
                f.write(s)
    
    def save(self):
        if self._filepath:
            os.makedirs(os.path.dirname(self._filepath) or ".", exist_ok=True)
            with open(self._filepath, "w", encoding="utf-8") as f:
                f.write(self._content)

invalid = ComboCheck()
checked = ComboCheck()
locked = ComboCheck()