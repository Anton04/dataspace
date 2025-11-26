import json
import xloil as xlo

@xlo.func
def get_json_table(json_text: str):
    """
    Takes a JSON list of objects and returns a 2D table:
    Row 1: formula in caller cell + keys
    Rows below: values per object, "" if key missing
    """

    # --- Parse JSON ---
    try:
        data = json.loads(json_text)
    except Exception as e:
        return [[f"JSON error: {e}"]]

    if not isinstance(data, list):
        return [["Input is not a JSON list"]]

    if len(data) == 0:
        return [["(empty list)"]]

    # --- Collect all keys ---
    keys = set()
    for obj in data:
        if isinstance(obj, dict):
            keys.update(obj.keys())
        else:
            return [["List contains non-object:", str(obj)]]

    keys = sorted(keys)

    # --- Get formula from caller cell ---
    try:
        caller = xlo.Caller()
        addr = caller.address()          # e.g. 'Sheet1!R1C1' eller 'Sheet1!A1'
        rng = xlo.Range(addr)            # Gör om till Range
        formula = rng.formula            # Detta är själva formeln
    except Exception:
        formula = ""                     # Fallback om något går fel (t.ex. ej från ark)

    #Ta sista delen av formeln efter . om den innehåller $
    if "$" in formula and "." in formula:
        mainkey = formula.split(".")[-1].split("\"")[0]

    #Extract the topic by finding mqtt:// and using everthing after that until "
    topic = "mqtt://" + formula.split("mqtt://")[-1].split('"')[0]

    formattetvalue = mainkey + " (from: " + topic + ")"

    # --- Build table ---
    # Första rad: formel i första kolumnen, tomma i resten
    header_row0 = [formattetvalue] 
    # Andra rad: nycklar
    header_row1 = keys

    table = [header_row0, header_row1]

    # Resterande rader: värden per objekt
    for obj in data:
        row = [obj.get(k, "") for k in keys]
        table.append(row)

    return table


@xlo.func
def render_json_table(json_text: str):

    # -----------------------------
    # Parse JSON
    # -----------------------------
    try:
        data = json.loads(json_text)
    except Exception as e:
        return f"JSON error: {e}"

    if not isinstance(data, list):
        return "Input is not a JSON list"

    if len(data) == 0:
        data = []

    # -----------------------------
    # Collect keys
    # -----------------------------
    keys = set()
    for obj in data:
        if isinstance(obj, dict):
            keys.update(obj.keys())
        else:
            return f"Non-object element: {obj}"
    keys = sorted(keys)

    # ============================================
    # FIRST: Caller info (sheet, row0, col0)
    # ============================================
    caller = xlo.Caller()
    full_addr = caller.address()      # "Sheet1!B7"

    if "!" not in full_addr:
        return "Invalid caller address"

    sheet_name, cell_addr = full_addr.split("!")

    # Split A1 into column letters and row number
    import re
    m = re.match(r"([A-Za-z]+)([0-9]+)", cell_addr)
    if not m:
        return "Invalid A1 address"
    col_letters, row_str = m.groups()
    row0 = int(row_str)

    # Convert col letters to index
    def col_letters_to_index(letters: str) -> int:
        v = 0
        for ch in letters.upper():
            v = v * 26 + (ord(ch) - 64)
        return v

    col0 = col_letters_to_index(col_letters)

    # Convert index to column letters
    def col_index_to_letters(idx: int) -> str:
        s = ""
        while idx > 0:
            idx, r = divmod(idx - 1, 26)
            s = chr(65 + r) + s
        return s

    def make_cell(c_idx, r_idx):
        return f"{col_index_to_letters(c_idx)}{r_idx}"

    # ============================================
    # SECOND: Compute table dimensions
    # ============================================
    table_width  = max(1, len(keys))     # at least one col
    table_height = 2 + len(data)         # header + keys + rows
    height_to_check = table_height + 1   # one extra row

    start_row = row0 + 1    # row under formula
    start_col = col0

    # ============================================
    # THIRD: Empty region check
    # ============================================
    for r in range(height_to_check):
        for c in range(table_width):
            addr = f"{sheet_name}!{make_cell(start_col + c, start_row + r)}"
            val = xlo.Range(addr).value
            if val not in (None, ""):
                return f"#ERR: Cannot write JSON table because cell {addr} is not empty."

    # ============================================
    # FOURTH: Extract metadata from formula
    # ============================================
    caller_range = xlo.Range(full_addr)
    formula = caller_range.formula or ""

    mainkey = ""
    if "." in formula and "$" in formula:
        mainkey = formula.split(".")[-1].split('"')[0]

    topic = ""
    if "mqtt://" in formula:
        topic = "mqtt://" + formula.split("mqtt://")[-1].split('"')[0]

    formatted_value = f"{mainkey} (from: {topic})"

    # ============================================
    # FIFTH: Write table into sheet
    # ============================================
    try:
        # Header under formula
        target = f"{sheet_name}!{make_cell(col0, row0 + 1)}"
        #xlo.Range(target).value = formatted_value

        # Keys row
        for i, k in enumerate(keys):
            tgt = f"{sheet_name}!{make_cell(col0 + i, row0 + 2)}"
            xlo.Range(tgt).value = k

        # Data rows
        for r, obj in enumerate(data):
            for c, k in enumerate(keys):
                v = obj.get(k, "")
                tgt = f"{sheet_name}!{make_cell(col0 + c, row0 + 3 + r)}"
                xlo.Range(tgt).value = v

    except Exception as e:
        return f"Write failed: {e}"

    return formatted_value



def is_region_empty(sheet_name, col0, row0, width, height):
    """
    Checks if a region is empty (all None or empty string).
    width  = number of columns
    height = number of rows
    """
    for r in range(height):
        for c in range(width):
            cell_addr = f"{sheet_name}!{make_cell(col0 + c, row0 + r)}"
            val = xlo.Range(cell_addr).value
            if val not in (None, ""):
                return False
    return True

