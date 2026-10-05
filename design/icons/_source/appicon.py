from icons import *
def app_icon():
    g = glasses(0)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect x="8" y="8" width="112" height="112" rx="26" fill="#1e2a36"/>
  <rect x="8" y="64" width="112" height="56" rx="26" fill="#243443"/>
  <rect x="8" y="64" width="112" height="28" fill="#243443"/>
  <g transform="translate(24 20) scale(5)"><path d="{g}" fill="#f5f7f9" fill-rule="evenodd"/></g>
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M64 108 V92 C64 84 56 80 44 76" stroke="#5b6b7b" stroke-width="7"/>
    <path d="M64 108 V92 C64 84 72 80 84 76" stroke="#f4a63a" stroke-width="7"/>
  </g>
  <circle cx="86" cy="75" r="6" fill="#f4a63a"/>
</svg>
'''
if __name__ == '__main__':
    import cairosvg
    s = app_icon(); open('app.scambio.Scambio.svg','w').write(s)
    cairosvg.svg2png(bytestring=s.encode(), write_to='app.png', output_width=256)
