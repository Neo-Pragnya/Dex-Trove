# Verification

## 1. Visual: headless screenshots with frames

```bash
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"   # or: google-chrome / chromium
"$C" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=4000 \
     --window-size=1400,1800 --screenshot=home.png http://localhost:4321/
```

- Use a tall window so below-the-fold reveals are on screen at load (the kit reveals in-viewport elements on a
  timer, independent of IntersectionObserver).
- To force a light or dark scheme: `--blink-settings=preferredColorScheme=1` (light) or `0` (dark).

## 2. Phone width

Headless Chrome on macOS will not shrink a window below ~500 px. Render the page inside 390 px iframes instead:

```html
<!-- phone.html, served from the same origin -->
<body style="margin:0;display:flex;gap:10px">
  <iframe src="/" style="width:390px;height:1400px;border:0"></iframe>
  <iframe src="/catalog/" style="width:390px;height:1400px;border:0"></iframe>
</body>
```

Check for horizontal scrolling. Every wide element (tables, code) needs its own `overflow-x:auto`.

## 3. Reduced motion / static mode

`?motion=static` makes the kit behave as if `prefers-reduced-motion: reduce` were set: reveals show instantly,
morphs jump to their target, and the field draws one still frame. Use it for deterministic screenshots and diffs.

## 4. Interaction logic

`--dump-dom` advances only **one animation frame**, so animated morphs appear unchanged there. Test the
*wiring* in static mode instead, by dispatching events and writing results into the DOM:

```html
<a id="host" href="#"><svg id="g" viewBox="0 0 100 100" data-morph="circle>star"></svg></a>
<script src="motion-kit.js"></script>
<script>
  addEventListener("load", () => {
    const d = () => document.querySelector("#g path").getAttribute("d");
    const before = d();
    document.getElementById("host").dispatchEvent(new PointerEvent("pointerenter"));
    setTimeout(() => (document.body.dataset.result = "morphed=" + (d() !== before)), 300);
  });
</script>
```

```bash
"$C" --headless=new --virtual-time-budget=3000 --dump-dom "file://$PWD/t.html?motion=static" | grep -o 'data-result="[^"]*"'
# data-result="morphed=true"
```

## 5. Checklist

- [ ] Hero renders with shapes; the headline is readable over them (shapes stay behind with low opacity)
- [ ] Every card glyph has a distinct rest shape per category
- [ ] Count-ups end on the exact number
- [ ] No horizontal scroll at 390 px
- [ ] `?motion=static` screenshot shows everything (nothing stuck invisible)
- [ ] Keyboard focus triggers the same morph as hover (the kit listens to `focusin`)
- [ ] Text contrast ≥ 4.5:1 (ink colours, not pastels, for text)
