import asyncio
from pathlib import Path
import subprocess
import imageio_ffmpeg
import edge_tts

ROOT = Path(r"D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10")
OUT = ROOT / "Georaster-19-10"
VOICE = "ar-SA-ZariyahNeural"

TEXTS = {
"1": """في هذا الفيديو أشرح خطوات كشف المباني داخل جيو رستر.

أفتح قسم Map and Analysis، ثم أختار AI Object Detection، وبعدها وظيفة Buildings.

في البداية أختار Local orthophoto كمصدر للصورة. أضغط على Upload GeoTIFF وأحدد صورة RGB الجوية. يتحقق التطبيق من عدد القنوات، نوع الصورة، نظام الإحداثيات، والمعلومات الجغرافية قبل بدء المعالجة.

بعد نجاح التحقق تظهر الصورة الجوية في سير العمل. من قائمة Building model أختار نموذج كشف المباني المتاح. تبقى إعدادات النموذج متوافقة مع GeoRaster، بما في ذلك المعالجة المسبقة وحجم المربعات.

أراجع Probability threshold وأتركه عند القيمة الظاهرة في اللوحة عندما أريد الإعداد القياسي.

الآن أضغط Run Building detection. يجهز التطبيق الصورة، يحولها إلى RGB، يقسمها إلى مربعات متداخلة، ثم يشغل النموذج على كل مربع.

ينتج النموذج خريطة احتمالية للمباني. بعد ذلك يدمج GeoRaster نتائج المربعات ويطبق العتبة، ثم ينظف النتيجة ويحّول القناع إلى Building polygons مرتبطة بالإحداثيات الحقيقية للصورة.

تظهر المضلعات فوق الصورة الجوية مباشرة. أراجع موقع المباني، حدودها، وأي مبانٍ صغيرة أو مناطق تحتاج إلى فحص.

في قسم النتائج أراجع Candidate count وTotal area وMean area وMedian area وMin area وMax area وPerimeter.

بعد الانتهاء أستخدم أدوات التصدير لإنشاء GeoJSON أو CSV أو Metadata JSON أو ZIP، مع بقاء النتيجة ظاهرة على خريطة GeoRaster.""",
"2": """في هذا الفيديو أشرح سير عمل تحليل الراستر في GeoRaster خطوة بخطوة.

أبدأ من Map and Analysis، ثم أحدد Start date وEnd date، وأختار Sentinel-2 من قائمة Satellite sensor، مع تحديد Export resolution.

أرسم Area of interest على الخريطة. بعد ذلك أضغط Search images. يعرض GeoRaster الصور المتاحة، فأختار الصورة المناسبة وأضغط Show on map.

في لوحة Analysis تظهر كل منتجات الراستر. أبدأ بـ NDVI، وهو مؤشر الغطاء النباتي، ثم أستطيع اختيار NDBI للمناطق المبنية والأسطح غير المنفذة.

أختار NDWI للمياه، وBSI للتربة العارية، وSAVI لقياس الغطاء النباتي مع تقليل تأثير التربة.

تظهر أيضا OSI-SAR عندما أحتاج إلى تحليل يعتمد على بيانات الرادار. أما Delta NDVI وDelta NDWI وDelta NDBI وDelta BSI وDelta SAVI فهي تحليلات تغير تقارن القيم بين فترتين زمنيتين.

إذا كان الهدف تصنيف الغطاء الأرضي، أختار Supervised Classification أو Unsupervised Classification من نفس اللوحة.

عند اختيار أي مؤشر، يعرض GeoRaster وصفه والفرق بينه وبين المنتجات الأخرى. بعد ذلك أضغط Run raster analysis.

يحسب التطبيق النتيجة داخل منطقة الاهتمام ويعرضها كطبقة ملونة على الخريطة. أراجع Legend وHistogram، ثم أتحقق من Min وMax وMedian وعدد البكسلات الصالحة وCoverage وQuality.

يمكنني تبديل المؤشر وإعادة الحساب ومقارنة الطبقات، ثم أستخدم أدوات التصدير لحفظ النتيجة بصيغة GeoTIFF أو CSV أو صورة أو PDF.""",
}

async def main():
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for key in ["2"]:
        text = TEXTS[key]
        audio = OUT / f"{key}_georaster_arabic_voiceover.mp3"
        await edge_tts.Communicate(text, VOICE, rate="-10%").save(str(audio))
        duration = "180.16" if key == "1" else "204.57"
        output = OUT / f"{key}_georaster_arabic_explained.mp4"
        subprocess.run([ffmpeg, "-y", "-i", str(ROOT / f"{key}.mp4"), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "apad", "-t", duration, str(output)], check=True)
        print(output)

asyncio.run(main())
