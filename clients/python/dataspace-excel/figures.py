import xloil as xlo

@xlo.func
def rotera_figur(namn: str, vinkel: float):
    xl = xlo.app()
    shape = xl.ActiveSheet.Shapes(namn)
    shape.Rotation = vinkel      # grader, 0–360
    return f"Figuren '{namn}' är nu roterad {vinkel}°"
