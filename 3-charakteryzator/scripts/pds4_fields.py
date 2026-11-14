"""Print the field layout of a PDS4 label (.xml): number, name, unit, description."""
import re, sys
def fields(path):
    txt = open(path, errors='replace').read()
    out = []
    for blk in re.findall(r'<Field_(?:Delimited|Character)>(.*?)</Field_(?:Delimited|Character)>', txt, flags=re.S):
        def g(k):
            m = re.search(r'<' + k + r'>(.*?)</' + k + r'>', blk, flags=re.S)
            return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
        out.append((g('field_number'), g('name'), g('unit'), g('data_type'), g('missing_constant') or g('invalid_constant'), g('description')))
    return out, txt
if __name__ == '__main__':
    w = 200
    for p in sys.argv[1:]:
        if p.startswith('-w'): w = int(p[2:]); continue
        fl, txt = fields(p)
        print('==', p.split('/')[-1], len(fl), 'fields')
        for f in fl: print(f"{f[0]:>3} {f[1]:<34} u={f[2]:<10} {f[3][:14]:<14} miss={f[4]:<8} {f[5][:w]}")
