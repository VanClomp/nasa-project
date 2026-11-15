"""Print the column layout of a PDS3 label (.lbl): name, bytes, unit, missing flag, description."""
import re, sys
def columns(path):
    txt = open(path, errors='replace').read()
    out = []
    for blk in re.split(r'OBJECT\s*=\s*(?:COLUMN|FIELD)', txt)[1:]:
        blk = re.split(r'END_OBJECT', blk)[0]
        def g(k):
            m = re.search(r'^\s*' + k + r'\s*=\s*("[^"]*"|\S+)', blk, flags=re.M)
            return re.sub(r'\s+', ' ', m.group(1).strip('"')).strip() if m else ''
        out.append(dict(name=g('NAME'), start=g('START_BYTE'), bytes=g('BYTES'), unit=g('UNIT'), type=g('DATA_TYPE'),
                        missing=g('MISSING_CONSTANT') or g('INVALID_CONSTANT') or g('NULL_CONSTANT') or g('MISSING'), desc=g('DESCRIPTION')))
    return out, txt
if __name__ == '__main__':
    w = 170
    for p in sys.argv[1:]:
        if p.startswith('-w'): w = int(p[2:]); continue
        cols, txt = columns(p)
        hdr = {k: (re.search(r'^\s*' + k + r'\s*=\s*(.+)$', txt, flags=re.M) or [None, ''])[1].strip() for k in ('ROWS', 'ROW_BYTES')}
        print('==', p.split('/')[-1], hdr)
        for i, c in enumerate(cols, 1):
            print(f"{i:2d} {c['name']:<26} b{c['start']:>4}+{c['bytes']:<3} {c['type'][:11]:<11} u={c['unit'][:10]:<10} miss={c['missing'][:9]:<9} {c['desc'][:w]}")
