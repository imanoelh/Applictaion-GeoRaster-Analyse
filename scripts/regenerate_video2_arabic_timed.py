import asyncio
from pathlib import Path
import subprocess
import imageio_ffmpeg
import edge_tts

ROOT = Path(r"D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10")
OUT = ROOT / "Georaster-19-10"
VOICE = "ar-SA-ZariyahNeural"
FF = imageio_ffmpeg.get_ffmpeg_exe()

SEGMENTS = [
    ("01", 25, "نبدأ في جيو رستر من قسم الخريطة والتحليل. أحدد تاريخ البداية والنهاية، أختار Sentinel-2، ثم أحدد دقة التصدير. بعد ذلك أفتح أداة رسم منطقة الاهتمام وأحدد المستطيل الذي ستتم داخله عملية البحث والحساب."),
    ("02", 30, "أضغط على Search images، فتظهر صور Sentinel-2 المتاحة. أختار الصورة المناسبة من القائمة، ثم أضغط Show on map حتى تظهر الصورة ومنطقة الاهتمام على الخريطة. الآن أصبحت الصورة جاهزة لتحليل الراستر."),
    ("03", 38, "أبدأ بمؤشر NDVI لقياس الغطاء النباتي. يعرض التطبيق وصف المؤشر، ثم أضغط Run raster analysis. تظهر طبقة NDVI بألوان متدرجة، وأراجع وسيلة الإيضاح والنتائج والإحصاءات، مثل الحد الأدنى والحد الأقصى والمتوسط والمساحة وعدد البكسلات والمدرج التكراري."),
    ("04", 30, "بعد ذلك أختار NDBI، وهو مؤشر المناطق المبنية والأسطح غير المنفذة. أضغط Run raster analysis، فيعرض جيو رستر دليل المناطق المبنية فوق الخريطة، مع فئات مثل عدم وجود دليل مبني، سطح غير منفذ محتمل، منطقة مبنية، ومنطقة مبنية عالية الثقة."),
    ("05", 25, "أنتقل إلى BSI، وهو مؤشر التربة العارية. أختار BSI ثم أشغل التحليل. يوضح العرض المناطق ذات التوقيع القوي للتربة الجافة، مع وسيلة إيضاح وإحصاءات المساحة والمدرج التكراري."),
    ("06", 28, "أختار SAVI لتحليل الغطاء النباتي مع تقليل تأثير التربة. بعد تشغيل التحليل تظهر طبقة SAVI، وتعرض النتائج فئات الغطاء النباتي من النادر جدا إلى الكثيف، مع القيم والإحصاءات الخاصة بالمنطقة."),
    ("07", 28, "تظل لوحة التحليل متاحة لاختيار NDWI للمياه، وOSI-SAR لتحليل الرادار، وتحليلات التغير Delta NDVI وDelta NDWI وDelta NDBI وDelta BSI وDelta SAVI. كما تتوفر Supervised Classification وUnsupervised Classification. بعد اختيار أي منتج أستخدم Run أو Recalculate، ثم أراجع الخريطة والنتائج وأصدر GeoTIFF أو Map PNG أو PDF Report أو CSV stats."),
]

async def main():
    padded = []
    for name, seconds, text in SEGMENTS:
        raw = OUT / f"v2_ar_{name}.mp3"
        pad = OUT / f"v2_ar_{name}_pad.m4a"
        if not raw.exists() or raw.stat().st_size < 1000:
            for attempt in range(4):
                try:
                    await edge_tts.Communicate(text, VOICE, rate="-15%").save(str(raw))
                    if raw.stat().st_size >= 1000:
                        break
                except Exception:
                    if attempt == 3:
                        raise
                await asyncio.sleep(1.5)
        subprocess.run([FF, "-y", "-i", str(raw), "-af", f"apad=pad_dur={seconds}", "-t", str(seconds), "-c:a", "aac", "-b:a", "128k", str(pad)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        padded.append(pad)
    concat = OUT / "v2_ar_concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in padded), encoding="utf-8")
    audio = OUT / "2_georaster_arabic_voiceover_timed.m4a"
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(audio)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    output = OUT / "2_georaster_arabic_explained_timed.mp4"
    subprocess.run([FF, "-y", "-i", str(ROOT / "2.mp4"), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "apad", "-t", "204.57", str(output)], check=True)
    print(output)

asyncio.run(main())
