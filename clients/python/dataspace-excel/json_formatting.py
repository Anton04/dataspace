import json
import re
import xloil as xlo
import re
import traceback

# ============================================================
#  Helper functions (column conversions)
# ============================================================

def col_letters_to_index(letters: str) -> int:
    v = 0
    for ch in letters.upper():
        v = v * 26 + (ord(ch) - 64)
    return v

def col_index_to_letters(idx: int) -> str:
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s

def make_cell(c_idx: int, r_idx: int) -> str:
    return f"{col_index_to_letters(c_idx)}{r_idx}"

# ============================================================
#  Helper: Check if region is EMPTY
# ============================================================

def is_region_empty(sheet_name: str, col0: int, row0: int, width: int, height: int) -> bool:
    """
    Returns True if ALL cells in the region are empty (None or "").
    col0 and row0 are 1-based numeric col/row.
    width and height are number of columns/rows to check.
    """
    for r in range(height):
        for c in range(width):
            addr = f"{sheet_name}!{make_cell(col0 + c, row0 + r)}"
            val = xlo.Range(addr).value
            if val not in (None, ""):
                return False
    return True

# ============================================================
#  Helper: extract formatted header metadata
# ============================================================

def extract_formatted_value(full_addr: str) -> str:
    try:
        formula = xlo.Range(full_addr).formula or ""
    except:
        formula = ""

    mainkey = ""
    if "." in formula and "$" in formula:
        mainkey = formula.split(".")[-1].split('"')[0]

    topic = ""
    if "mqtt://" in formula:
        part = formula.split("mqtt://")[-1]
        topic = "mqtt://" + re.split(r'["$]', part)[0]

    return f"{mainkey} (from: {topic})"

# ============================================================
#  FUNCTION 1: get_json_table
# ============================================================

@xlo.func
def get_json_table(json_text: str):

    try:
        data = json.loads(json_text)
    except Exception as e:
        return [[f"JSON error: {e}"]]

    # Caller metadata
    try:
        caller = xlo.Caller()
        full_addr = caller.address()
    except:
        full_addr = None

    formatted_header = extract_formatted_value(full_addr) if full_addr else ""

    # ----------------------- DICT CASE -----------------------
    if isinstance(data, dict):
        keys = sorted(data.keys())
        table = [[formatted_header]]
        for k in keys:
            table.append([k, data.get(k, "")])
        return table

    # ------------------------ LIST CASE -----------------------
    if not isinstance(data, list):
        return [["Input is not JSON list or dict"]]

    if len(data) == 0:
        return [["(empty list)"]]

    # Collect ALL keys
    keys = set()
    for obj in data:
        if not isinstance(obj, dict):
            return [["Non-object element:", str(obj)]]
        keys.update(obj.keys())
    keys = sorted(keys)

    table = [[formatted_header], keys]
    for obj in data:
        table.append([obj.get(k, "") for k in keys])

    return table

# ============================================================
#  FUNCTION 2: render_json_table
# ============================================================

@xlo.func
def render_json_table(json_text: str,target_area = None):

    try:
        data = json.loads(json_text)
    except Exception as e:
        return f"JSON error: {e}"

    if not isinstance(data, (dict, list)):
        return "Input must be JSON dict or list"

    # Caller info
    caller = xlo.Caller()
    full_addr = caller.address()

    if "!" not in full_addr:
        return "Invalid caller address"

    sheet_name, cell_addr = full_addr.split("!")

    m = re.match(r"([A-Za-z]+)([0-9]+)", cell_addr)
    if not m:
        return "Invalid A1 address"

    col_letters, row_str = m.groups()
    row0 = int(row_str)
    col0 = col_letters_to_index(col_letters)

    formatted_value = extract_formatted_value(full_addr)

    # Startposition för tabellen
    start_row = row0 + 1
    start_col = col0

    # --------------------------------------------------------
    # CASE 1: dict → vertical table
    # --------------------------------------------------------
    if isinstance(data, dict):
        keys = sorted(data.keys())

        table_width = 2
        table_height = len(keys) + 1

        # EMPTY CHECK
        if not is_region_empty(sheet_name, start_col, start_row, table_width, table_height):
            return "#ERR: Target region not empty."

        # RESET FORMAT (oavsett vad som funnits tidigare)
        reset_area_format(sheet_name, start_col, start_row)

        # Write header
        safe_write(sheet2, start_col, start_row, formatted_value)

        # Write rows
        for i, k in enumerate(keys):
            safe_write(sheet2, start_col, start_row + 1 + i, k)
            safe_write(sheet2, start_col + 1, start_row + 1 + i, data.get(k, ""))

        return "Json table rendered."

    # --------------------------------------------------------
    # CASE 2: list of dicts → horizontal table
    # --------------------------------------------------------
    if len(data) == 0:
        return formatted_value

    # Collect keys
    keys = set()
    for obj in data:
        if not isinstance(obj, dict):
            return f"Non-object element: {obj}"
        keys.update(obj.keys())
    keys = sorted(keys)

    table_width  = len(keys)
    table_height = 2 + len(data)

    # EMPTY CHECK
    if not is_region_empty(sheet_name, start_col, start_row, table_width, table_height):
        return "#ERR: Target region not empty."

    # RESET FORMAT (måste göras även här)
    reset_area_format(sheet_name, start_col, start_row)

    # Write header
    xlo.Range(f"{sheet_name}!{make_cell(start_col, start_row)}").value = formatted_value

    # Key row (later bold)
    for i, k in enumerate(keys):
        a1_addr = f"{sheet_name}!{make_cell(start_col + i, start_row + 1)}"
        xlo.Range(a1_addr).value = k

    # Values
    for r, obj in enumerate(data):
        for c, k in enumerate(keys):
            v = obj.get(k, "")
            xlo.Range(f"{sheet_name}!{make_cell(start_col + c, start_row + 2 + r)}").value = v

    # Make header bold
    try:
        first_hdr = make_cell(start_col, start_row + 1)
        last_hdr  = make_cell(start_col + table_width - 1, start_row + 1)
        rng_header = xlo.app().Range(f"{sheet_name}!{first_hdr}:{last_hdr}")
        rng_header.Font.Bold = True
    except Exception:
        pass

    return "Json table rendered."


def reset_area_format(sheet_name, start_col, start_row, max_width=30, max_height=300):
    """
    Rensar fetstil och bakgrundsfärg i ett område.
    Används för att rensa gammal formatering oavsett om vi ska skriva dict eller list.
    """
    try:
        first_cell = make_cell(start_col, start_row)
        last_cell  = make_cell(start_col + max_width - 1,
                               start_row + max_height - 1)

        rng = xlo.app().Range(f"{sheet_name}!{first_cell}:{last_cell}")
        rng.Font.Bold = False
        rng.Interior.ColorIndex = 0
    except Exception:
        # Ignorera om COM är låst, kör ändå vidare
        pass

def parse_target_range(rng):
    """
    Tar ett xlOil range-objekt och returnerar:
      sheet_name, start_col, start_row, end_col, end_row
    """
    full_addr = rng.address()  # t.ex. "Sheet1!C31:H50"
    sheet_name, cells = full_addr.split("!")

    if ":" in cells:
        start_addr, end_addr = cells.split(":")
    else:
        start_addr = end_addr = cells

    m1 = re.match(r"([A-Za-z]+)([0-9]+)", start_addr)
    m2 = re.match(r"([A-Za-z]+)([0-9]+)", end_addr)

    start_col = col_letters_to_index(m1.group(1))
    start_row = int(m1.group(2))
    end_col = col_letters_to_index(m2.group(1))
    end_row = int(m2.group(2))

    return sheet_name, start_col, start_row, end_col, end_row

def parse_range_from_formula(formula: str, sep: str):
    """
    Hittar andra argumentet (range) i en formel som:
      =render_json_table2(sync_data("...";"...");C31:H50)

    Strategi:
      - ta bort '='
      - ta bort sista ')'
      - splitta från slutet på sep (rsplit)
      - andra delen är range-uttrycket
    Returnerar t.ex. "C31:H50" eller "Blad1!C31:H50",
    eller None om inget andra argument finns.
    """

    if not formula:
        return None

    # Ta bort inledande '=' och trimma
    f = formula.lstrip("=").strip()

    # Måste sluta med ')', annars orkar vi inte tolka
    if not f.endswith(")"):
        return None

    # Ta bort sista ')'
    f = f[:-1].rstrip()

    # Splitta från höger på separatorn, max en gång
    parts = f.rsplit(sep, 1)
    if len(parts) < 2:
        # Inget sep på top-nivå hittat → inget range-argument
        return None

    area_expr = parts[1].strip()

    # Ex: "C31:H50" eller "Blad1!C31:H50"
    return area_expr

import re

def col_letters_to_index(letters: str) -> int:
    v = 0
    for ch in letters.upper():
        v = v * 26 + (ord(ch) - 64)
    return v

def parse_area_string(area_str: str):
    """
    Tolkar en område-sträng av typen:
      "Sheet1!C31:H50"
      "C31:H50"

    Returnerar:
      (sheet_name, start_col, start_row, end_col, end_row)
    """

    # Trim whitespace
    s = area_str.strip()

    # Finns ett '!' ?
    if "!" in s:
        sheet_name, coord = s.split("!")
    else:
        sheet_name = None
        coord = s

    # Dela t.ex. "C31:H50"
    if ":" not in coord:
        raise ValueError(f"Invalid range expression: '{coord}'")

    left, right = coord.split(":")

    # Matcha "C31"
    m1 = re.match(r"([A-Za-z]+)([0-9]+)", left)
    m2 = re.match(r"([A-Za-z]+)([0-9]+)", right)

    if not (m1 and m2):
        raise ValueError(f"Invalid cell coordinate in '{coord}'")

    col1, row1 = m1.groups()
    col2, row2 = m2.groups()

    start_col = col_letters_to_index(col1)
    end_col   = col_letters_to_index(col2)
    start_row = int(row1)
    end_row   = int(row2)

    return sheet_name, start_col, start_row, end_col, end_row

def safe_write(sheet, col, row, value):
    """Write only if different."""
    addr = f"{sheet}!{make_cell(col, row)}"
    rng = xlo.Range(addr)
    old = rng.value
    if old != value:
        rng.value = value

def clear_unused_area(sheet, start_col, start_row, end_col, end_row,
                      table_width, table_height):
    """
    Clears all cells in the target area EXCEPT those used by the table.
    """
    for c in range(start_col, end_col + 1):
        for r in range(start_row, end_row + 1):
            used = (
                c < start_col + table_width and
                r < start_row + table_height
            )
            if not used:
                addr = f"{sheet}!{make_cell(c, r)}"
                rng = xlo.Range(addr)
                if rng.value not in ("", None):
                    rng.value = ""
            



@xlo.func
def render_json_table2(json_text: str, target_area=None):
    """
    Tvåläges-funktion:

    A) =render_json_table2(json)
       → auto-mode: räkna area, kolla tomhet, skriv om formeln
       → returnera header text

    B) =render_json_table2(json; C10:H20)
       → write-mode: läs range ur formeln (inte target_area)
       → skriv tabell i området
       → partial rendering tillåten
       → returnera fel om området är för litet
    """

    # -----------------------------
    # PARSE JSON
    # -----------------------------
    try:
        data = json.loads(json_text)
    except Exception as e:
        return f"JSON error: {e}"

    if not isinstance(data, (dict, list)):
        return "Input must be JSON dict or list"

    # -----------------------------
    # CALLER INFO
    # -----------------------------
    caller_addr = xlo.Caller().address()         # t.ex. "Sheet1!B7"
    sheet_name, caller_cell = caller_addr.split("!")

    formatted_value = extract_formatted_value(caller_addr)

    # -----------------------------
    # AUTO-DETECT ARGUMENT SEPARATOR
    # -----------------------------
   
    sep = ","

    # -----------------------------
    # PARSE RANGE OUT OF FORMULA
    # -----------------------------
    caller_range = xlo.Range(caller_addr)
    formula_text = caller_range.formula

    #Has range or None
    has_range = target_area != None


    # -----------------------------
    # COMPUTE TABLE SIZE
    # -----------------------------
    def compute_table_size(d):
        if isinstance(d, dict):
            return (2, len(d) + 1)   # (width, height)
        else:
            keys = sorted({k for o in d if isinstance(o, dict) for k in o.keys()})
            return (len(keys), 2 + len(d))

    table_width, table_height = compute_table_size(data)


    #Find range string and parse it
    # if no , in formula → no range  separator is alwas ,
    sep_index = formula_text.find(",")
    if sep_index == -1:
        area_str = None
    else:
        area_str = formula_text[sep_index + 1:-1]

    #print formula text
    print("Formula text: " +str(formula_text))

    #print area string
    print("Area string from formula: " +str(area_str))
  

    # ============================================================
    # MODE A — AUTO-MODE (NO RANGE IN FORMULA)
    # ============================================================
    if not area_str:

        # Parse caller cell
        m = re.match(r"([A-Za-z]+)([0-9]+)", caller_cell)
        col_letters = m.group(1)
        row0 = int(m.group(2))
        start_col = col_letters_to_index(col_letters)
        start_row = row0 + 1

        # Check if region is empty
        if not is_region_empty(sheet_name, start_col, start_row,
                               table_width, table_height):
            return "#ERR: Target region not empty."

        # Compute final area (for rewriting formula)
        first_cell = make_cell(start_col, start_row)
        last_cell = make_cell(start_col + table_width - 1,
                              start_row + table_height - 1)

        area_str = f'{sheet_name}!{first_cell}:{last_cell}'

        #print area string
        print("Computed area string: " +area_str)

        #print original formula
        print("Original formula: " +formula_text)

        formula = formula_text[:-1] + f',{area_str})'

        print("Resulting formula: " +formula)

        # Rewrite own formula
        #new_formula = f'=render_json_table2("{json_text}"{sep}{area_str2})'

        try:
            print("Rewriting formula to: " +formula)
            xlo.app().Range(caller_addr).Formula = formula
        except Exception as e:
            return "#ERR: Could not rewrite formula" + traceback.format_exc()
        
  


    

    # ============================================================
    # MODE B — WRITE-MODE (EXPLICIT RANGE IN FORMULA)
    # ============================================================
    sheet2, start_col, start_row, end_col, end_row = parse_area_string(area_str)

    clear_unused_area(
        sheet2,
        start_col,
        start_row,
        end_col,
        end_row,
        table_width,
        table_height
    )

    avail_width = end_col - start_col + 1
    avail_height = end_row - start_row + 1

    too_small = (table_width > avail_width) or (table_height > avail_height)

    # -----------------------------
    # DICT-MODE (VERTICAL)
    # -----------------------------
    if isinstance(data, dict):

        keys = sorted(data.keys())

        # header
        safe_write(sheet2, start_col, start_row, formatted_value)

        # rows (partial allowed)
        max_rows = min(len(keys), avail_height - 1)

        for i in range(max_rows):
            k = keys[i]

            if start_col <= end_col:
                safe_write(sheet2, start_col, start_row + 1 + i, k)
            if start_col + 1 <= end_col:
                safe_write(sheet2, start_col + 1, start_row + 1 + i, data[k])

        return "#ERR: Area too small" if too_small else "Rendered dict."


    # -----------------------------
    # LIST-MODE (HORIZONTAL)
    # -----------------------------
    keys = sorted({k for o in data if isinstance(o, dict) for k in o.keys()})

    # header cell
    safe_write(sheet2, start_col, start_row, formatted_value)

   # keys row
    max_cols = min(len(keys), avail_width)
    for i in range(max_cols):
        safe_write(sheet2, start_col + i, start_row + 1, keys[i])
        # Bold header
        try:
            xlo.app().Range(f"{sheet2}!{make_cell(start_col + i, start_row + 1)}").Font.Bold = True
        except:
            pass

    # values
    max_rows = min(len(data), avail_height - 2)
    for r in range(max_rows):
        obj = data[r]
        for c in range(max_cols):
            safe_write(sheet2,
                    start_col + c,
                    start_row + 2 + r,
                    obj.get(keys[c], ""))

    return "#ERR: Area too small" if too_small else "Rendered list."


