#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 SVG 的 <marker> 展开成真实图形——给不认 marker 的渲染器补箭头。

**为什么要有它。** macOS 的 sips 走 ImageIO / CoreSVG，渐变、虚线、斜纹、中文
全画得对，唯独不实现 SVG 1.1 的 <marker>。而法律关系图、庭审对抗图、重画模块
的方向全靠 marker-end，sips 一过手箭头全掉，线成了光头——关系的方向是有法律
意义的，不能丢。（实测 relation 模块 demo.svg：11 个 marker-end，直转后 0 个。）

**做法。** 读 <marker> 定义，在每个引用元素的端点按切线方向贴一份 marker 图形，
再把 marker-end / marker-start 属性去掉，避免渲染器重复画。

**边界。**
- 只处理 marker-end / marker-start；marker-mid 罕见，跳过（上游七家都没用）。
- markerUnits 两种都支持：userSpaceOnUse 与 strokeWidth。
- marker 内图形支持 path / polygon / rect / circle / line。
- 带 viewBox 的 marker 会按 markerWidth / markerHeight 缩放，与浏览器一致。
- 元素支持 path / line / polyline / polygon，闭合与非闭合写法都认。
- orient：auto 取端点切线；auto-start-reverse 在 marker-start 时反向。

    python3 svg_marker.py 图.svg                  展开到 图.arrows.svg
    python3 svg_marker.py 图.svg 出.svg            指定输出
    python3 svg_marker.py 图.svg 出.svg --png 出.png   顺手用 sips 出 PNG
"""
import math
import os
import re
import subprocess
import sys

NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
ELEM = re.compile(r'<(path|line|polyline|polygon)\b([^>]*?)(/?)>', re.S)


def _attrs(s):
    return dict(ATTR.findall(s))


def _f(v, default=0.0):
    try:
        return float(re.match(NUM, str(v).strip()).group(0))
    except (AttributeError, ValueError, TypeError):
        return default


def parse_markers(svg):
    """id -> {refX, refY, units, scale, shapes:[(tag, attrs)]}"""
    out = {}
    for m in re.finditer(r'<marker\b([^>]*)>(.*?)</marker>', svg, re.S):
        head, body = _attrs(m.group(1)), m.group(2)
        mid = head.get('id')
        if not mid:
            continue
        shapes = []
        for sm in re.finditer(r'<(path|polygon|rect|circle|line)\b([^>]*?)/?>', body, re.S):
            a = _attrs(sm.group(2))
            if a:
                shapes.append((sm.group(1), a))
        if not shapes:
            continue
        # viewBox 存在时，marker 内容要缩放到 markerWidth×markerHeight 的视口里
        scale = 1.0
        vb = head.get('viewBox')
        if vb:
            nums = [float(x) for x in re.findall(NUM, vb)]
            if len(nums) == 4 and nums[2] and nums[3]:
                mw = _f(head.get('markerWidth', 3), 3) or 3
                mh = _f(head.get('markerHeight', 3), 3) or 3
                scale = min(mw / nums[2], mh / nums[3])
        out[mid] = {
            'refX': _f(head.get('refX', 0)),
            'refY': _f(head.get('refY', 0)),
            'units': head.get('markerUnits', 'strokeWidth'),
            'scale': scale,
            'orient': head.get('orient', '0'),
            'shapes': shapes,
        }
    return out


def path_points(d):
    """按顺序取出 d 里的坐标点，够算端点切线就行。"""
    pts = []
    cx = cy = 0.0
    start = (0.0, 0.0)
    tokens = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(' + NUM + r')', d)

    def flush(cmd, vals):
        nonlocal cx, cy, start
        if cmd is None or not vals:
            return
        u, rel = cmd.upper(), cmd.islower()
        if u == 'M':
            for i in range(0, len(vals) - 1, 2):
                x, y = vals[i], vals[i + 1]
                if rel:
                    x, y = cx + x, cy + y
                cx, cy = x, y
                pts.append((cx, cy))
                if i == 0:
                    start = (cx, cy)
        elif u in ('L', 'T'):
            for i in range(0, len(vals) - 1, 2):
                x, y = vals[i], vals[i + 1]
                if rel:
                    x, y = cx + x, cy + y
                cx, cy = x, y
                pts.append((cx, cy))
        elif u == 'H':
            for v in vals:
                cx = cx + v if rel else v
                pts.append((cx, cy))
        elif u == 'V':
            for v in vals:
                cy = cy + v if rel else v
                pts.append((cx, cy))
        elif u in ('C', 'S', 'Q'):
            step = 6 if u == 'C' else 4
            for i in range(0, len(vals) - step + 1, step):
                x, y = vals[i + step - 2], vals[i + step - 1]
                if rel:
                    x, y = cx + x, cy + y
                cx, cy = x, y
                pts.append((cx, cy))
        elif u == 'A':
            for i in range(0, len(vals) - 6, 7):
                x, y = vals[i + 5], vals[i + 6]
                if rel:
                    x, y = cx + x, cy + y
                cx, cy = x, y
                pts.append((cx, cy))
        elif u == 'Z':
            cx, cy = start
            pts.append((cx, cy))

    cmd, vals = None, []
    for tok_cmd, tok_num in tokens:
        if tok_cmd:
            flush(cmd, vals)
            cmd, vals = tok_cmd, []
        elif tok_num:
            vals.append(float(tok_num))
    flush(cmd, vals)
    return pts


def point_list(raw):
    """polyline / polygon 的 points 属性 → [(x,y)]"""
    nums = [float(x) for x in re.findall(NUM, raw or '')]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _direction(pts, at_end=True):
    """返回 (端点 x, y, 切线角)。端点处没有长度时返回 None。"""
    if len(pts) < 2:
        return None
    if at_end:
        ex, ey = pts[-1]
        rest = list(reversed(pts[:-1]))
    else:
        ex, ey = pts[0]
        rest = list(pts[1:])
    for px, py in rest:
        if abs(px - ex) > 1e-6 or abs(py - ey) > 1e-6:
            ang = math.degrees(math.atan2(ey - py, ex - px))
            return ex, ey, ang if at_end else ang + 180.0
    return None


def _shape_svg(tag, a):
    fill = a.get('fill', '#000')
    if fill == 'none' and 'stroke' not in a:
        return ''
    if tag == 'path':
        extra = ' stroke="%s"' % a['stroke'] if 'stroke' in a else ''
        if 'stroke-width' in a:
            extra += ' stroke-width="%s"' % a['stroke-width']
        return '<path d="%s" fill="%s"%s/>' % (a.get('d', ''), fill, extra)
    if tag == 'polygon':
        return '<polygon points="%s" fill="%s"/>' % (a.get('points', ''), fill)
    if tag == 'polyline':
        return '<polyline points="%s" fill="none" stroke="%s"/>' % (
            a.get('points', ''), a.get('stroke', fill))
    if tag == 'circle':
        return ('<circle cx="%s" cy="%s" r="%s" fill="%s"/>'
                % (a.get('cx', 0), a.get('cy', 0), a.get('r', 1), fill))
    if tag == 'rect':
        return ('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>'
                % (a.get('x', 0), a.get('y', 0), a.get('width', 1), a.get('height', 1), fill))
    if tag == 'line':
        return ('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s"/>'
                % (a.get('x1', 0), a.get('y1', 0), a.get('x2', 0), a.get('y2', 0),
                   a.get('stroke', fill)))
    return ''


def _transform(mk, ex, ey, ang, stroke_width):
    scale = stroke_width if mk['units'] == 'strokeWidth' else 1.0
    scale *= mk.get('scale', 1.0)
    tf = 'translate(%.3f,%.3f) rotate(%.3f)' % (ex, ey, ang)
    if abs(scale - 1.0) > 1e-9:
        tf += ' scale(%.4g)' % scale
    return tf + ' translate(%.4g,%.4g)' % (-mk['refX'], -mk['refY'])


def expand(svg):
    """返回 (展开后的 svg 文本, 处理的箭头数)。没有 marker 就原样返回。"""
    markers = parse_markers(svg)
    if not markers:
        return svg, 0

    added, count = [], 0

    def repl(m):
        nonlocal count
        tag, body, selfclosed = m.group(1), m.group(2), m.group(3)
        attrs = _attrs(body)
        if tag == 'path':
            pts = path_points(attrs.get('d', ''))
        elif tag in ('polyline', 'polygon'):
            pts = point_list(attrs.get('points'))
        else:                                      # line
            pts = [(0, 0), (0, 0)]
            try:
                pts = [(_f(attrs.get('x1')), _f(attrs.get('y1'))),
                       (_f(attrs.get('x2')), _f(attrs.get('y2')))]
            except Exception:
                return m.group(0)
        if len(pts) < 2:
            return m.group(0)
        sw = _f(attrs.get('stroke-width', 1), 1.0) or 1.0
        hit = False
        for prop, at_end in (('marker-end', True), ('marker-start', False)):
            ref = attrs.get(prop)
            if not ref:
                continue
            mid = re.search(r'url\(#([^)]+)\)', ref)
            if not mid or mid.group(1) not in markers:
                continue
            mk = markers[mid.group(1)]
            info = _direction(pts, at_end)
            if not info:
                continue
            ex, ey, ang = info
            if not at_end and mk.get('orient') == 'auto-start-reverse':
                ang += 180.0
            inner = ''.join(_shape_svg(t, a) for t, a in mk['shapes'])
            if not inner:
                continue
            added.append('<g transform="%s" pointer-events="none">%s</g>'
                         % (_transform(mk, ex, ey, ang, sw), inner))
            hit = True
            count += 1
        if not hit:
            return m.group(0)
        cleaned = re.sub(r'\s*marker-(?:end|start)="[^"]*"', '', m.group(0))
        return cleaned

    out = ELEM.sub(repl, svg)
    if added:
        # 展开的图形统一追加在 </svg> 之前；没有 </svg> 就追加到末尾
        if '</svg>' in out:
            out = out.replace('</svg>', ''.join(added) + '</svg>', 1)
        else:
            out += ''.join(added)
    return out, count


def expand_file(src, dst=None):
    """展开一份 SVG 文件。返回 (输出路径, 箭头数)；没有箭头时返回 (src, 0)。"""
    with open(src, encoding='utf-8') as f:
        svg = f.read()
    out, n = expand(svg)
    if not n:
        return src, 0
    if dst is None:
        base, ext = os.path.splitext(src)
        dst = base + '.arrows' + (ext or '.svg')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(out)
    return dst, n


def main(argv):
    if len(argv) < 1 or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0 if argv else 2
    src = argv[0]
    if not os.path.isfile(src):
        print('！找不到 %s' % src, file=sys.stderr)
        return 2
    dst = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else None
    png = argv[argv.index('--png') + 1] if '--png' in argv else None

    try:
        out, n = expand_file(src, dst)
    except (OSError, UnicodeDecodeError) as e:
        print('！读不了 %s：%s' % (src, e), file=sys.stderr)
        return 1
    if not n:
        print('这份 SVG 没有 marker 箭头，原样可用：%s' % src)
    else:
        print('展开 %d 个箭头 → %s' % (n, out))
    if png:
        p = subprocess.run(['sips', '-s', 'format', 'png', out, '--out', png],
                           capture_output=True, text=True)
        print('sips：%s' % ('OK' if p.returncode == 0 else p.stderr.strip()))
        if p.returncode != 0:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
