"""Annotate a disposable F0 copy to identify the two leg layers for image editing."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).parent
im = Image.open(HERE / "generated_f0.png").convert("RGBA")
overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
d = ImageDraw.Draw(overlay)
try:
    font = ImageFont.truetype("arial.ttf", 46)
except OSError:
    font = ImageFont.load_default()

# On this F0 target, A is the near-side leg forward on the right; B is the
# far-side leg trailing on the left. These overlays are reference-only.
d.line([(672, 1057), (710, 1138), (772, 1216)], fill=(239, 35, 78, 220), width=16, joint="curve")
d.ellipse((722, 1178, 887, 1302), outline=(239, 35, 78, 230), width=12)
d.rounded_rectangle((867, 1147, 951, 1221), radius=12, fill=(255, 255, 255, 230))
d.text((884, 1152), "A", fill=(220, 20, 65, 255), font=font, stroke_width=2, stroke_fill="white")

d.line([(518, 1058), (461, 1117), (459, 1172)], fill=(20, 145, 224, 220), width=16, joint="curve")
d.ellipse((385, 1139, 538, 1277), outline=(20, 145, 224, 230), width=12)
d.rounded_rectangle((319, 1134, 398, 1208), radius=12, fill=(255, 255, 255, 230))
d.text((338, 1139), "B", fill=(0, 120, 210, 255), font=font, stroke_width=2, stroke_fill="white")

overlayed = Image.alpha_composite(im, overlay)
overlayed.save(HERE / "F0_leg_identity_markup.png")
