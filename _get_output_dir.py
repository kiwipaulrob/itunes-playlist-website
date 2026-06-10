"""Helper used by upload_site.bat — prints output_dir from config.ini."""
import configparser, pathlib, sys

ini = pathlib.Path(__file__).parent / "config.ini"
c = configparser.ConfigParser(interpolation=None)
c.read(ini, encoding="utf-8")
v = c.get("paths", "output_dir", fallback="").strip()
print(v)
