from __future__ import annotations

import re
from typing import Any


REPORT_AR: dict[str, str] = {
    "Page": "الصفحة",
    "Professional raster analysis report": "تقرير احترافي لتحليل البيانات الراسترية",
    "GeoRaster Analytics Platform - Report automatically generated from raster analysis results.": "منصة GeoRaster للتحليلات - تقرير مولّد آلياً من نتائج تحليل البيانات الراسترية.",
    "Execution time": "وقت إنشاء التقرير",
    "Sensor": "المستشعر",
    "Study area": "منطقة الدراسة",
    "Selected area of interest": "منطقة الاهتمام المحددة",
    "Analysis period": "فترة التحليل",
    "Surface": "المساحة",
    "GeoRasterPortal version": "إصدار GeoRasterPortal",
    "Description of the executed index": "وصف التحليل المنفّذ",
    "Description of the executed analysis": "وصف التحليل المنفّذ",
    "Scientific introduction, principle, interpretation, and context of use": "مقدمة علمية ومبدأ المعالجة والتفسير ومجالات الاستخدام",
    "Principle": "المبدأ",
    "Spectral contrast / thematic clustering": "التباين الطيفي / التجميع الموضوعاتي",
    "Interpretation": "التفسير",
    "Low, medium, and high values by legend": "تُفسَّر القيم والفئات وفقاً لمفتاح الخريطة",
    "Use case": "مجال الاستخدام",
    "Study area information": "معلومات منطقة الدراسة",
    "Area of interest, sensor, acquisition dates, source, and spatial resolution": "منطقة الاهتمام والمستشعر وتواريخ الاقتناء ومصدر البيانات والدقة المكانية",
    "Area name": "اسم المنطقة",
    "Coordinates / extent": "الإحداثيات / الامتداد المكاني",
    "Acquisition period": "فترة الاقتناء",
    "Source data": "مصدر البيانات",
    "Spatial resolution": "الدقة المكانية",
    "Analysis type": "نوع التحليل",
    "Satellite Images": "المرئيات الفضائية",
    "Satellite image of reference": "المرئية الفضائية المرجعية",
    "Result of the analysis": "نتيجة التحليل",
    "Statistics and Interpretation": "الإحصاءات والتفسير",
    "Legend": "مفتاح الخريطة",
    "Class colours, surface, and percentage of each class": "ألوان الفئات ومساحة كل فئة ونسبتها من المنطقة المحللة",
    "Statistics": "الإحصاءات",
    "Minimum, maximum, mean, standard deviation, pixels, and total mapped area": "القيمة الدنيا والعظمى والمتوسط والانحراف المعياري وعدد البكسلات وإجمالي المساحة الممثلة",
    "Minimum": "القيمة الدنيا",
    "Maximum": "القيمة العظمى",
    "Mean": "المتوسط",
    "Std. dev.": "الانحراف المعياري",
    "Pixels": "عدد البكسلات",
    "Total area": "المساحة الإجمالية",
    "Dominant class": "الفئة السائدة",
    "Detailed interpretation": "التفسير التفصيلي",
    "Clear and concise reading of the result": "قراءة علمية واضحة وموجزة للنتيجة",
    "Conclusion": "الخلاصة",
    "Reference multispectral image": "المرئية المرجعية متعددة الأطياف",
    "Analysis result": "نتيجة التحليل",
    "Reference image unavailable": "المرئية المرجعية غير متاحة",
    "Result image unavailable": "مرئية النتيجة غير متاحة",
    "Change Detection Visual Results": "النتائج الخرائطية لكشف التغيرات",
    "Baseline classified index map": "خريطة المؤشر المصنّف للفترة المرجعية",
    "Comparison classified index map": "خريطة المؤشر المصنّف لفترة المقارنة",
    "Delta map: period 2 minus period 1": "خريطة الفرق: الفترة الثانية ناقص الفترة الأولى",
    "Period": "الفترة",
    "Classified map": "الخريطة المصنّفة",
    "Final change detection result": "النتيجة النهائية لكشف التغيرات",
}


ANALYSIS_LABELS_AR: dict[str, str] = {
    "NDVI": "مؤشر الاختلاف المعياري للغطاء النباتي (NDVI)",
    "NDWI": "مؤشر الاختلاف المعياري للمياه (NDWI)",
    "NDBI": "مؤشر الاختلاف المعياري للمناطق المبنية (NDBI)",
    "BSI": "مؤشر التربة العارية (BSI)",
    "SAVI": "مؤشر الغطاء النباتي المعدّل بحسب التربة (SAVI)",
    "OSI_SAR": "مؤشر الاشتباه في البقع النفطية بالرادار (OSI-SAR)",
    "OIL_SPILL_SUSPECT_INDEX": "مؤشر الاشتباه في البقع النفطية بالرادار (OSI-SAR)",
    "CHANGE_NDVI": "كشف تغير الغطاء النباتي باستخدام NDVI",
    "CHANGE_NDWI": "كشف تغير المياه والرطوبة باستخدام NDWI",
    "CHANGE_NDBI": "كشف تغير المناطق المبنية باستخدام NDBI",
    "CHANGE_BSI": "كشف تغير انكشاف التربة باستخدام BSI",
    "CHANGE_SAVI": "كشف تغير الغطاء النباتي باستخدام SAVI",
    "CHANGE_DETECTION_NDVI": "كشف تغير الغطاء النباتي باستخدام NDVI",
    "CHANGE_DETECTION_NDWI": "كشف تغير المياه والرطوبة باستخدام NDWI",
    "CHANGE_DETECTION_NDBI": "كشف تغير المناطق المبنية باستخدام NDBI",
    "CHANGE_DETECTION_BSI": "كشف تغير انكشاف التربة باستخدام BSI",
    "CHANGE_DETECTION_SAVI": "كشف تغير الغطاء النباتي باستخدام SAVI",
    "SUPERVISED_CLASSIFICATION": "التصنيف الموجّه للغطاء الأرضي",
    "UNSUPERVISED_CLASSIFICATION": "التصنيف غير الموجّه للغطاء الأرضي",
}


ANALYSIS_PROFILES_AR: dict[str, dict[str, str]] = {
    "NDVI": {
        "full_name": "مؤشر الاختلاف المعياري للغطاء النباتي (NDVI)",
        "principle": "يُحسب من التباين بين انعكاس الأشعة تحت الحمراء القريبة والنطاق الأحمر لتقدير وجود الغطاء النباتي النشط ضوئياً وكثافته وحيويته.",
        "bands": "Sentinel-2: ‏B8 للأشعة تحت الحمراء القريبة وB4 للأحمر. Landsat 8/9: ‏SR_B5 وSR_B4.",
        "objective": "تقييم كثافة الغطاء النباتي وحيويته وتباينه المكاني داخل منطقة الدراسة.",
        "interpretation": "تشير القيم المنخفضة عادةً إلى تربة عارية أو غطاء نباتي متناثر أو أسطح غير نباتية، بينما تشير القيم المرتفعة إلى غطاء نباتي كثيف أو نشط.",
        "applications": "مراقبة الغطاء النباتي والتقييم الزراعي ورصد الجفاف وتدهور الأراضي ودراسة النظم البيئية.",
    },
    "NDWI": {
        "full_name": "مؤشر الاختلاف المعياري للمياه (NDWI)",
        "principle": "يعتمد على التباين الطيفي بين النطاق الأخضر والأشعة تحت الحمراء القريبة لإبراز المياه السطحية ومؤشرات الرطوبة.",
        "bands": "Sentinel-2: ‏B3 للأخضر وB8 للأشعة تحت الحمراء القريبة. Landsat 8/9: ‏SR_B3 وSR_B5.",
        "objective": "اكتشاف المسطحات المائية والأسطح الرطبة والبكسلات ذات المحتوى الرطوبي المرتفع.",
        "interpretation": "ترتبط القيم المنخفضة غالباً بالأسطح الجافة أو غير المائية، بينما تشير القيم المرتفعة إلى المياه المفتوحة أو الرطوبة السطحية القوية.",
        "applications": "رسم المسطحات المائية ورصد الفيضانات والأراضي الرطبة والخزانات وتقييم الري.",
    },
    "NDBI": {
        "full_name": "مؤشر الاختلاف المعياري للمناطق المبنية (NDBI)",
        "principle": "يستخدم التباين بين الأشعة تحت الحمراء قصيرة الموجة والأشعة تحت الحمراء القريبة لإبراز الأسطح المبنية وغير المنفذة.",
        "bands": "Sentinel-2: ‏B11 للأشعة تحت الحمراء قصيرة الموجة وB8 للأشعة تحت الحمراء القريبة. Landsat 8/9: ‏SR_B6 وSR_B5.",
        "objective": "تحديد أنماط التوسع العمراني والأسطح غير المنفذة والغطاء الأرضي الاصطناعي.",
        "interpretation": "تشير القيم المنخفضة غالباً إلى المياه أو الغطاء النباتي أو الأسطح غير المبنية، بينما تعكس القيم المرتفعة استجابة عمرانية أو أسطحاً غير منفذة.",
        "applications": "تحليل النمو الحضري ورصد استعمالات الأراضي ورسم البنية التحتية وتقييم الأسطح غير المنفذة.",
    },
    "BSI": {
        "full_name": "مؤشر التربة العارية (BSI)",
        "principle": "يدمج النطاقات المرئية والأشعة تحت الحمراء القريبة وقصيرة الموجة لفصل التربة المكشوفة عن الأسطح النباتية أو الرطبة.",
        "bands": "Sentinel-2: ‏B11 وB4 وB8 وB2. Landsat 8/9: ‏SR_B6 وSR_B4 وSR_B5 وSR_B2.",
        "objective": "إبراز التربة المكشوفة والأراضي الجافة والرمال والمناطق ضعيفة الغطاء.",
        "interpretation": "تشير القيم المنخفضة إلى أسطح نباتية أو رطبة، بينما تشير القيم المرتفعة إلى انكشاف قوي للتربة أو الأسطح المعدنية الجافة.",
        "applications": "رسم التربة العارية ودراسات التعرية وتدهور الأراضي ورصد التعدين والإنشاءات والبيئات الجافة.",
    },
    "SAVI": {
        "full_name": "مؤشر الغطاء النباتي المعدّل بحسب التربة (SAVI)",
        "principle": "يخفف تأثير خلفية التربة بإضافة معامل تصحيح إلى التباين بين النطاق الأحمر والأشعة تحت الحمراء القريبة.",
        "bands": "Sentinel-2: ‏B8 وB4. Landsat 8/9: ‏SR_B5 وSR_B4.",
        "objective": "قياس كثافة الغطاء النباتي وحيويته في المناطق التي يؤثر فيها انعكاس التربة بقوة في NDVI.",
        "interpretation": "تشير القيم المنخفضة إلى غطاء نباتي ضعيف أو تربة مكشوفة، بينما تشير القيم المرتفعة إلى غطاء نباتي أكثر كثافة وحيوية.",
        "applications": "مراقبة الزراعة والغطاء النباتي المتناثر والبيئات شبه الجافة وتدهور الأراضي.",
    },
    "SUPERVISED_CLASSIFICATION": {
        "full_name": "التصنيف الموجّه للغطاء الأرضي",
        "principle": "يستخدم عينات تدريب موسومة ومتغيرات طيفية لإسناد كل بكسل إلى فئة موضوعاتية محددة مسبقاً.",
        "bands": "نطاقات طيفية ومؤشرات مشتقة، تشمل عادةً النطاقات المرئية والأشعة تحت الحمراء القريبة وقصيرة الموجة ومؤشرات NDVI وNDWI وNDBI وBSI وSAVI.",
        "objective": "إنتاج خريطة موضوعاتية للغطاء الأرضي داخل منطقة الاهتمام المحددة.",
        "interpretation": "قيم الفئات وصفية وليست ترتيباً عددياً للشدة؛ لذلك تُفسَّر النتيجة وفقاً لمفتاح الخريطة ومقاييس الدقة.",
        "applications": "رسم الغطاء الأرضي والتخطيط البيئي والدراسات الحضرية والزراعة ودعم القرار المكاني.",
    },
    "UNSUPERVISED_CLASSIFICATION": {
        "full_name": "التصنيف غير الموجّه للغطاء الأرضي",
        "principle": "يجمع البكسلات وفق تشابهها الطيفي من دون استخدام فئات تدريب موسومة مسبقاً.",
        "bands": "نطاقات طيفية ومؤشرات مشتقة، تشمل عادةً النطاقات المرئية والأشعة تحت الحمراء القريبة وقصيرة الموجة ومؤشرات NDVI وNDWI وNDBI وBSI وSAVI.",
        "objective": "اكتشاف الأنماط الطيفية السائدة وإنتاج مجموعات استكشافية للغطاء الأرضي.",
        "interpretation": "أرقام المجموعات معرفات داخلية وليست قيماً للشدة؛ ويعتمد تفسيرها على التوقيعات الطيفية ومفتاح الخريطة.",
        "applications": "الرسم الاستكشافي السريع واستطلاع الغطاء الأرضي والتحليل التمهيدي قبل التصنيف.",
    },
    "OSI_SAR": {
        "full_name": "مؤشر الاشتباه في البقع النفطية بالرادار ذي الفتحة التركيبية (OSI-SAR)",
        "principle": "يحلل شذوذ التشتت الخلفي في مرئيات Sentinel-1 الرادارية، ولا سيما الأهداف الداكنة فوق المياه، لتحديد بقع سطحية محتملة.",
        "bands": "استقطابا VV وVH من Sentinel-1 مع التباين المحلي ومرشحات السياق المكاني.",
        "objective": "تحديد وترتيب البقع الداكنة المشتبه بها تمهيداً للتحقق الإضافي.",
        "interpretation": "تعبر الفئات عن درجات اشتباه وليست إثباتاً لوجود تلوث نفطي؛ ويلزم التحقق باستخدام الرياح والسياق البحري والمرئيات البصرية.",
        "applications": "المراقبة البحرية والمسح الأولي للتلوث ورصد السواحل ودعم الاستجابة للطوارئ.",
    },
}


for _index, _subject in {
    "CHANGE_NDVI": ("NDVI", "الغطاء النباتي", "رصد فقدان الغطاء النباتي أو استقراره أو تحسنه بين فترتين."),
    "CHANGE_NDWI": ("NDWI", "المياه والرطوبة السطحية", "رصد فقدان المياه أو تغير الرطوبة أو زيادة المسطحات المائية بين فترتين."),
    "CHANGE_NDBI": ("NDBI", "المناطق المبنية", "رصد انخفاض أو استقرار أو زيادة استجابة NDBI بين فترتين، دون اعتبار الزيادة إثباتاً لعمران جديد."),
    "CHANGE_BSI": ("BSI", "انكشاف التربة العارية", "رصد زيادة التربة المكشوفة أو استقرارها أو تراجعها بين فترتين."),
    "CHANGE_SAVI": ("SAVI", "الغطاء النباتي المعدّل بحسب التربة", "رصد تغير الغطاء النباتي في البيئات الجافة وشبه الجافة بين فترتين."),
}.items():
    _base, _subject_name, _objective = _subject
    ANALYSIS_PROFILES_AR[_index] = {
        "full_name": ANALYSIS_LABELS_AR[_index],
        "principle": f"يقارن {_base} المحسوب للفترة الأولى بالقيمة المناظرة للفترة الثانية ضمن منطقة الدراسة نفسها.",
        "bands": f"النطاقات والمشتقات الطيفية المستخدمة في حساب {_base} لكلتا الفترتين.",
        "objective": _objective,
        "interpretation": f"تدل القيم السالبة على انخفاض {_subject_name}، والقيم القريبة من الصفر على الاستقرار النسبي، والقيم الموجبة على الزيادة بين الفترتين.",
        "applications": "التحليل متعدد الأزمنة ورصد التحولات المكانية ودعم التخطيط والمتابعة البيئية.",
    }


LEGEND_AR: dict[str, str] = {
    "Water": "مياه",
    "Open water": "مياه مفتوحة",
    "Open water or permanent water surfaces.": "مياه مفتوحة أو مسطحات مائية دائمة.",
    "Open water and permanent water surfaces.": "مياه مفتوحة أو مسطحات مائية دائمة.",
    "Natural vegetation": "غطاء نباتي طبيعي",
    "Shrubland, grassland, and natural vegetation.": "أراضٍ شجيرية وعشبية وغطاء نباتي طبيعي.",
    "Agriculture": "أراضٍ زراعية",
    "Cropland, irrigated parcels, and cultivated areas.": "محاصيل وقطع زراعية مروية ومناطق مزروعة.",
    "Forest": "غابات",
    "Tree cover and dense forest vegetation.": "غطاء شجري ونباتات غابية كثيفة.",
    "Built-up": "مناطق مبنية",
    "Built-up area": "منطقة مبنية",
    "Urban, industrial, road, and impervious surfaces.": "أسطح حضرية وصناعية وطرق وأسطح غير منفذة.",
    "Bare soil": "تربة عارية",
    "Bare soil / sand": "تربة عارية / رمال",
    "Exposed soil, sand, and mineral surfaces.": "تربة مكشوفة ورمال وأسطح معدنية.",
    "Wetlands": "أراضٍ رطبة",
    "Wetland": "أرض رطبة",
    "Wetlands, marshes, and mixed water vegetation.": "أراضٍ رطبة ومستنقعات وغطاء نباتي مائي مختلط.",
    "Cloud or shadow": "سحب أو ظلال",
    "Cloud, cloud shadow, snow, or no-data samples.": "سحب أو ظلال سحب أو ثلوج أو عينات بلا بيانات.",
    "No or very sparse vegetation cover": "غطاء نباتي معدوم أو متناثر جداً",
    "Sparse vegetation cover": "غطاء نباتي متناثر",
    "Moderate vegetation cover": "غطاء نباتي متوسط الكثافة",
    "Dense vegetation cover": "غطاء نباتي كثيف",
    "Very dense vegetation cover": "غطاء نباتي شديد الكثافة",
    "Bare or non-vegetated surfaces with very sparse vegetation.": "أسطح عارية أو غير نباتية مع غطاء نباتي متناثر جداً.",
    "Sparse or potentially stressed vegetation.": "غطاء نباتي متناثر أو يحتمل تعرضه للإجهاد.",
    "Moderate vegetation density.": "كثافة نباتية متوسطة.",
    "Dense vegetation cover.": "غطاء نباتي كثيف.",
    "Very dense and vigorous vegetation cover.": "غطاء نباتي شديد الكثافة وعالي الحيوية.",
    "Dry bare soil / non-water": "تربة عارية جافة / أسطح غير مائية",
    "Low moisture or vegetation": "رطوبة منخفضة أو غطاء نباتي",
    "Moist vegetation / wet soil": "غطاء نباتي رطب / تربة رطبة",
    "Shallow or mixed water": "مياه ضحلة أو مختلطة",
    "Non-built-up": "مناطق غير مبنية",
    "Low artificialization": "تحضر منخفض",
    "Probable built-up": "عمران محتمل",
    "Likely built-up": "عمران محتمل",
    "Dense built-up": "عمران كثيف",
    "Very low bare-soil exposure": "انكشاف منخفض جداً للتربة العارية",
    "Low bare-soil exposure": "انكشاف منخفض للتربة العارية",
    "Moderate bare-soil exposure": "انكشاف متوسط للتربة العارية",
    "High bare-soil exposure": "انكشاف مرتفع للتربة العارية",
    "Very high bare-soil exposure": "انكشاف مرتفع جداً للتربة العارية",
    "Bare soil or no vegetation": "تربة عارية أو غياب الغطاء النباتي",
    "Very sparse vegetation": "غطاء نباتي متناثر جداً",
    "Sparse semi-arid vegetation": "غطاء نباتي شبه جاف متناثر",
    "Moderate vegetation": "غطاء نباتي متوسط",
    "High vegetation vigor": "حيوية نباتية مرتفعة",
    "Very high vegetation vigor": "حيوية نباتية مرتفعة جداً",
    "No / very sparse vegetation": "غطاء نباتي معدوم أو ضعيف جداً",
    "Low vegetation": "غطاء نباتي ضعيف",
    "Dense vegetation": "غطاء نباتي كثيف",
    "Very dense vegetation": "غطاء نباتي شديد الكثافة",
    "Normal water": "مياه طبيعية",
    "Oil-spill suspect": "اشتباه بانسكاب نفطي",
    "Low oil-spill suspicion": "اشتباه منخفض في بقعة نفطية",
    "Medium oil-spill suspicion": "اشتباه متوسط في بقعة نفطية",
    "High oil-spill suspicion": "اشتباه مرتفع في بقعة نفطية",
    "Strong vegetation loss": "فقدان شديد للغطاء النباتي",
    "Moderate vegetation loss": "فقدان متوسط للغطاء النباتي",
    "Stable area": "منطقة مستقرة",
    "Moderate vegetation gain": "زيادة متوسطة في الغطاء النباتي",
    "Strong vegetation gain": "زيادة كبيرة في الغطاء النباتي",
    "Water/moisture disappearance": "اختفاء المياه أو الرطوبة",
    "Moisture decrease": "انخفاض الرطوبة",
    "Moisture increase": "زيادة الرطوبة",
    "Probable water appearance": "ظهور محتمل للمياه",
    "Strong NDBI decrease": "انخفاض شديد في استجابة NDBI",
    "Moderate NDBI decrease": "انخفاض متوسط في استجابة NDBI",
    "Moderate NDBI increase": "زيادة متوسطة في استجابة NDBI",
    "Strong NDBI increase": "زيادة شديدة في استجابة NDBI",
    "Built-up decrease": "انخفاض الدلائل العمرانية",
    "Low built-up decrease": "انخفاض عمراني محدود",
    "New artificialization": "توسع عمراني جديد",
    "Strong built-up expansion": "توسع عمراني شديد",
    "Strong bare-soil decrease": "انخفاض شديد في انكشاف التربة العارية",
    "Moderate bare-soil decrease": "انخفاض متوسط في انكشاف التربة العارية",
    "Moderate bare-soil increase": "زيادة متوسطة في انكشاف التربة العارية",
    "Strong bare-soil increase": "زيادة شديدة في انكشاف التربة العارية",
    "Strong vegetation-cover loss": "فقدان شديد للغطاء النباتي",
    "Moderate vegetation-cover loss": "فقدان متوسط للغطاء النباتي",
    "Moderate vegetation-cover gain": "زيادة متوسطة في الغطاء النباتي",
    "Strong vegetation-cover gain": "زيادة كبيرة في الغطاء النباتي",
    "Dense vegetation / trees": "غطاء نباتي كثيف / أشجار",
    "Crops / low vegetation": "محاصيل / غطاء نباتي منخفض",
    "Wetland / mixed class": "أرض رطبة / فئة مختلطة",
    "Uninterpreted cluster": "مجموعة غير مفسرة",
}


LEGEND_ALIASES: dict[str, str] = {
    "Absence ou tres faible couverture vegetale": "No or very sparse vegetation cover",
    "Couverture vegetale faible": "Sparse vegetation cover",
    "Couverture vegetale moyenne": "Moderate vegetation cover",
    "Couverture vegetale forte": "Dense vegetation cover",
    "Couverture vegetale tres forte": "Very dense vegetation cover",
    "Sec / non eau": "Dry bare soil / non-water",
    "Humidite faible": "Low moisture or vegetation",
    "Humidite moyenne": "Moist vegetation / wet soil",
    "Eau probable": "Open water",
    "Non bati": "Non-built-up",
    "Faible artificialisation": "Low artificialization",
    "Bati probable": "Likely built-up",
    "Bati dense": "Dense built-up",
}


DEFAULT_INTERPRETATIONS_AR: dict[str, str] = {
    "NDVI": "تصف النتيجة توزيع الغطاء النباتي داخل منطقة الاهتمام. تشير الفئات المرتفعة إلى غطاء نباتي كثيف أو نشط، بينما ترتبط الفئات المنخفضة بغطاء متناثر أو تربة عارية أو أسطح غير نباتية.",
    "NDWI": "تبرز النتيجة المياه السطحية والمناطق الرطبة. تشير الفئات المرتفعة إلى احتمال قوي لوجود المياه أو الرطوبة، بينما تمثل الفئات المنخفضة أسطحاً جافة أو غير مائية.",
    "NDBI": "تبرز النتيجة الدلائل الطيفية للمناطق المبنية والأسطح غير المنفذة، مع ضرورة التمييز بينها وبين التربة العارية بالاعتماد على مفتاح الخريطة والبيانات المساندة.",
    "BSI": "توضح النتيجة درجات انكشاف التربة العارية؛ وقد تمثل القيم المرتفعة تربة جافة أو رمالاً أو صخوراً أو أسطحاً معدنية ضعيفة الغطاء.",
    "SAVI": "تقيّم النتيجة الغطاء النباتي مع تقليل تأثير خلفية التربة، وهو ما يدعم تفسير المناطق شبه الجافة وضعيفة الغطاء.",
    "SUPERVISED_CLASSIFICATION": "تنتج عملية التصنيف الموجّه خريطة موضوعاتية للغطاء الأرضي اعتماداً على عينات التدريب والمتغيرات الطيفية. يجب تفسير الفئات وفق مفتاح الخريطة ومقاييس التحقق.",
    "UNSUPERVISED_CLASSIFICATION": "يجمع التصنيف غير الموجّه البكسلات في مجموعات طيفية متشابهة. تمثل النتيجة قراءة استكشافية ينبغي مراجعة دلالاتها الموضوعاتية قبل الاستخدام التشغيلي.",
    "OSI_SAR": "تعرض النتيجة أهدافاً رادارية داكنة مشتبه بها فوق المياه. تمثل الفئات درجات اشتباه وليست تأكيداً للتلوث النفطي، ويلزم التحقق من الرياح والسياق البحري والمرئيات البصرية.",
}


VALUE_MEANINGS_AR: dict[str, str] = {
    "NDVI": "تدل القيم المنخفضة على أسطح عارية أو غطاء نباتي متناثر، والمتوسطة على غطاء نباتي متوسط، والمرتفعة على غطاء نباتي كثيف أو عالي الحيوية",
    "NDWI": "تدل القيم المنخفضة على أسطح جافة أو غير مائية، والمتوسطة على بكسلات مختلطة أو رطبة، والمرتفعة على مياه مفتوحة أو رطوبة سطحية قوية",
    "NDBI": "تدل القيم المنخفضة على أسطح غير مبنية، والمتوسطة على حالات انتقالية، والمرتفعة على استجابة أقوى للمناطق المبنية أو الأسطح غير المنفذة",
    "BSI": "تدل القيم المنخفضة على أسطح نباتية أو رطبة، والمتوسطة على انكشاف جزئي للتربة، والمرتفعة على تربة عارية شديدة الانكشاف",
    "SAVI": "تدل القيم المنخفضة على غطاء نباتي متناثر أو غائب، والمتوسطة على غطاء متوسط، والمرتفعة على غطاء نباتي كثيف مع تقليل تأثير خلفية التربة",
    "SUPERVISED_CLASSIFICATION": "تُفسَّر قيم الفئات من خلال مفتاح الخريطة؛ فالرقم لا يعبر عن شدة الفئة وإنما يمثل رمزاً موضوعاتياً",
    "UNSUPERVISED_CLASSIFICATION": "تُفسَّر أرقام المجموعات من خلال مفتاح الخريطة والتوقيعات الطيفية، ولا يعبر ترتيبها العددي عن الشدة",
    "OSI_SAR": "تمثل الفئات درجات الاشتباه في الأهداف الرادارية الداكنة ولا تعني تأكيد وجود بقعة نفطية",
}


def normalize_language(value: Any) -> str:
    return "ar" if str(value or "").lower().startswith("ar") else "en"


def report_text(value: Any, language: str) -> str:
    text = "-" if value is None or value == "" else str(value)
    return REPORT_AR.get(text, text) if normalize_language(language) == "ar" else text


def analysis_label(value: Any) -> str:
    key = str(value or "").upper()
    return ANALYSIS_LABELS_AR.get(key, str(value or "-"))


def analysis_profile(value: Any) -> dict[str, str]:
    key = str(value or "").upper()
    profile = ANALYSIS_PROFILES_AR.get(key)
    if profile:
        return profile
    return {
        "full_name": analysis_label(value),
        "principle": "يعتمد التحليل على معالجة البيانات الراسترية والمتغيرات الطيفية المتاحة ضمن سير العمل المحدد.",
        "bands": "تتحدد النطاقات والمؤشرات المشتقة وفق نوع التحليل المختار.",
        "objective": "وصف النمط المكاني المكتشف داخل منطقة الدراسة.",
        "interpretation": "يجب تفسير النتيجة بالاعتماد على مفتاح الخريطة والإحصاءات والفئات الواردة في التقرير.",
        "applications": "إعداد التقارير ودعم القرار والتفسير الموضوعاتي للبيانات الراسترية.",
    }


def legend_text(value: Any) -> str:
    text = "-" if value is None or value == "" else str(value).strip()
    normalized = LEGEND_ALIASES.get(text, text)
    translated = LEGEND_AR.get(normalized)
    if translated:
        return translated
    cluster = re.match(r"^Cluster\s+(\d+)(?:\s*-\s*(.+))?$", normalized, flags=re.IGNORECASE)
    if cluster:
        suffix = legend_text(cluster.group(2)) if cluster.group(2) else ""
        return f"المجموعة {cluster.group(1)} - {suffix}" if suffix else f"المجموعة {cluster.group(1)}"
    thematic_class = re.match(r"^Class\s+(\d+)$", normalized, flags=re.IGNORECASE)
    if thematic_class:
        return f"الفئة {thematic_class.group(1)}"
    return normalized


def default_interpretation(value: Any) -> str:
    key = str(value or "").upper()
    if key.startswith("CHANGE_") or key.startswith("CHANGE_DETECTION_"):
        base = key.replace("CHANGE_DETECTION_", "").replace("CHANGE_", "")
        return f"تقارن عملية كشف التغير مؤشر {base} بين فترتين داخل منطقة الاهتمام نفسها. تشير الفئات السالبة إلى الانخفاض، والفئات المستقرة إلى تغير محدود، والفئات الموجبة إلى الزيادة بين الفترة الأولى والفترة الثانية."
    return DEFAULT_INTERPRETATIONS_AR.get(key, analysis_profile(value)["interpretation"])


def value_meaning(value: Any) -> str:
    key = str(value or "").upper()
    if key.startswith("CHANGE_") or key.startswith("CHANGE_DETECTION_"):
        base = key.replace("CHANGE_DETECTION_", "").replace("CHANGE_", "")
        return f"تدل القيم السالبة على انخفاض مؤشر {base}، والقيم القريبة من الصفر على الاستقرار النسبي، والقيم الموجبة على الزيادة بين الفترتين"
    return VALUE_MEANINGS_AR.get(key, "تُفسَّر القيم والفئات وفقاً لمفتاح الخريطة والسياق الموضوعاتي للتحليل")


def quality_conclusion() -> str:
    return "تتوافق النتيجة مع إعدادات التحليل المختارة والبيانات الراسترية المعالجة. وتعتمد موثوقية التفسير على جودة المرئيات والفترة الزمنية والغطاء السحابي ودقة عينات التحقق عند استخدامها."
