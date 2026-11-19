export const RESULT_LEGEND_AR: Record<string, string> = {
  "Water / negative values": "مياه أو قيم سالبة",
  "Bare soil / very dry desert": "تربة عارية أو صحراء شديدة الجفاف",
  "Very low vegetation activity": "نشاط نباتي منخفض جداً",
  "Low vegetation": "غطاء نباتي ضعيف",
  "Very dense vegetation": "غطاء نباتي شديد الكثافة",
  "< 0.00: water / negative values": "أقل من 0.00: مياه أو قيم سالبة",
  "Negative NDVI values, commonly water or non-vegetated surfaces.":
    "قيم NDVI سالبة، وغالباً ما تمثل مياهاً أو أسطحاً غير نباتية.",
  "0.00–0.05: bare soil / very dry desert": "0.00-0.05: تربة عارية أو صحراء شديدة الجفاف",
  "Bare soil or very dry desert response.": "استجابة تربة عارية أو صحراء شديدة الجفاف.",
  "0.05–0.10: very low vegetation activity": "0.05-0.10: نشاط نباتي منخفض جداً",
  "Very low vegetation activity.": "نشاط نباتي منخفض جداً.",
  "0.00–0.08: bare soil / very dry desert": "0.00–0.08: تربة عارية أو صحراء شديدة الجفاف",
  "0.08–0.15: very low vegetation activity": "0.08–0.15: نشاط نباتي منخفض جداً",
  "Very low vegetation activity or arid soil response.":
    "نشاط نباتي منخفض جداً أو استجابة لتربة قاحلة.",
  "0.15–0.25: very sparse vegetation": "0.15–0.25: غطاء نباتي متناثر جداً",
  "0.25–0.35: low vegetation": "0.25–0.35: غطاء نباتي منخفض",
  "0.35–0.50: moderate vegetation": "0.35–0.50: غطاء نباتي متوسط",
  "Strong multi-source built-up evidence.": "دليل قوي متعدد المصادر على وجود مناطق مبنية.",
  "0.10–0.20: very sparse vegetation": "0.10-0.20: غطاء نباتي متناثر جداً",
  "Very sparse vegetation cover.": "غطاء نباتي متناثر جداً.",
  "0.20–0.30: low vegetation": "0.20-0.30: غطاء نباتي ضعيف",
  "Low vegetation cover.": "غطاء نباتي ضعيف.",
  "0.30–0.50: moderate vegetation": "0.30-0.50: غطاء نباتي متوسط",
  "0.50–0.70: dense vegetation": "0.50-0.70: غطاء نباتي كثيف",
  ">= 0.70: very dense vegetation": "0.70 فأكثر: غطاء نباتي شديد الكثافة",
  "NDBI < -0.20: strong negative response": "NDBI أقل من -0.20: استجابة سالبة قوية",
  "NDBI < 0.00: non-built / vegetation / water": "NDBI أقل من 0.00: غير مبني / نبات / مياه",
  "0.00–0.05: transition / weak response": "0.00-0.05: انتقال / استجابة ضعيفة",
  "0.05–0.12: moderate positive": "0.05-0.12: استجابة موجبة متوسطة",
  ">= 0.12: strong positive": "0.12 فأكثر: استجابة موجبة قوية",
  "Non-built / vegetation / water": "غير مبني / نبات / مياه",
  "Transition / weak response": "انتقال / استجابة ضعيفة",
  "Moderate positive (possible built or bare)": "موجب متوسط (عمران محتمل أو تربة عارية)",
  "Strong positive (dense built or bright bare)": "موجب قوي (عمران كثيف أو تربة عارية ساطعة)",
  "Negative NDBI: vegetation, water, moisture, or shaded non-built surfaces.":
    "NDBI سالب: نباتات أو مياه أو رطوبة أو أسطح غير مبنية مظللة.",
  "Near-zero to weakly positive response; mixed or transitional surfaces.":
    "استجابة قريبة من الصفر أو موجبة ضعيفة؛ أسطح مختلطة أو انتقالية.",
  "Positive NDBI compatible with built-up or dry bare/mineral soil in arid landscapes.":
    "NDBI موجب يتوافق مع العمران أو التربة العارية/المعدنية الجافة في المناظر القاحلة.",
  "Strong positive SWIR response; dense built-up is likely but bright bare soil can look similar. Use Built-up detection for a stricter check.":
    "استجابة SWIR موجبة قوية؛ العمران الكثيف محتمل لكن التربة العارية الساطعة قد تبدو مشابهة. استخدم كشف المناطق المبنية للتحقق الأشد.",
  "Strong negative SWIR-to-NIR response; not a land-cover class by itself.":
    "استجابة سالبة قوية بين SWIR وNIR؛ ولا تمثل وحدها فئة غطاء أرضي.",
  "-0.20–0.00: negative response": "-0.20-0.00: استجابة سالبة",
  "Usually vegetation, moisture, water, or shaded surfaces.":
    "غالباً ما تمثل غطاء نباتياً أو رطوبة أو مياهاً أو أسطحاً مظللة.",
  "0.00–0.10: near-zero response": "0.00-0.10: استجابة قريبة من الصفر",
  "Mixed response where built-up and bare mineral surfaces may overlap.":
    "استجابة مختلطة قد تتداخل فيها الأسطح المبنية مع الأسطح المعدنية العارية.",
  "0.10–0.20: positive response": "0.10-0.20: استجابة موجبة",
  "Compatible with built-up or exposed mineral/bare surfaces.":
    "متوافقة مع الأسطح المبنية أو المعدنية المكشوفة أو العارية.",
  ">= 0.20: strong positive response": "0.20 فأكثر: استجابة موجبة قوية",
  "Strong SWIR response; verify with vegetation, water, and bare-soil information before interpreting as urban.":
    "استجابة SWIR قوية؛ يجب التحقق ببيانات الغطاء النباتي والمياه والتربة العارية قبل تفسيرها كمنطقة حضرية.",
  "Strong positive SWIR response; dense built-up is likely but bright bare soil can look similar.":
    "استجابة SWIR موجبة قوية؛ العمران الكثيف محتمل لكن التربة العارية الساطعة قد تبدو مشابهة.",
  "NDWI < -0.20: strong negative response": "NDWI أقل من -0.20: استجابة سالبة قوية",
  "0.00–0.10: transition": "0.00-0.10: استجابة انتقالية",
  "0.10–0.30: water-compatible response": "0.10-0.30: استجابة متوافقة مع المياه",
  ">= 0.30: strong water response": "0.30 فأكثر: استجابة مائية قوية",
  "BSI < -0.20: very negative": "BSI أقل من -0.20: استجابة سالبة جداً",
  "Very negative BSI response; interpretation depends on surface and atmosphere.":
    "استجابة BSI سالبة جداً؛ يعتمد تفسيرها على السطح والظروف الجوية.",
  "-0.20–0.00: negative": "-0.20-0.00: استجابة سالبة",
  "Negative BSI response, often covered or moist surfaces.":
    "استجابة BSI سالبة، وغالباً ما تمثل أسطحاً مغطاة أو رطبة.",
  "Transition response between covered and exposed surfaces.":
    "استجابة انتقالية بين الأسطح المغطاة والأسطح المكشوفة.",
  "0.10–0.20: probable bare soil": "0.10-0.20: تربة عارية محتملة",
  "Probable exposed bare soil response.": "استجابة محتملة لتربة عارية مكشوفة.",
  "≥ 0.20: strong bare-soil signature": "0.20 فأكثر: بصمة قوية للتربة العارية",
  "Strong exposed-soil or dry mineral response.": "استجابة قوية لتربة مكشوفة أو أسطح معدنية جافة.",
  "Strong negative NDBI response": "استجابة سالبة قوية لمؤشر NDBI",
  "Strong negative SWIR-to-NIR response; this value alone is not a land-cover class.":
    "استجابة سالبة قوية بين SWIR وNIR؛ ولا تمثل هذه القيمة بمفردها فئة للغطاء الأرضي.",
  "Negative SWIR-to-NIR response; usually vegetation, moisture, water, or shaded surfaces.":
    "استجابة سالبة بين SWIR وNIR؛ وغالباً ما ترتبط بالنباتات أو الرطوبة أو المياه أو الأسطح المظللة.",
  "NDBI response close to zero; built-up and bare mineral surfaces may overlap.":
    "استجابة NDBI قريبة من الصفر؛ وقد تتداخل فيها الأسطح المبنية مع الأسطح المعدنية العارية.",
  "Positive NDBI response compatible with built-up or exposed mineral/bare surfaces.":
    "استجابة NDBI موجبة تتوافق مع الأسطح المبنية أو المعدنية المكشوفة أو العارية.",
  "Strong positive SWIR response; verify with vegetation, water, and bare-soil information before interpreting as urban.":
    "استجابة SWIR موجبة قوية؛ يجب التحقق ببيانات النباتات والمياه والتربة العارية قبل تفسيرها كعمران.",
  "Strong negative NDWI response / probable dry land": "استجابة NDWI سالبة قوية / أرض جافة محتملة",
  "Negative NDWI response": "استجابة NDWI سالبة",
  "Transition / weak water response": "استجابة انتقالية / مائية ضعيفة",
  "Water-compatible NDWI response": "استجابة NDWI متوافقة مع المياه",
  "Strong water response": "استجابة مائية قوية",
  "Probable dry land or non-water surface.": "أرض جافة محتملة أو سطح غير مائي.",
  "Negative water response.": "استجابة مائية سالبة.",
  "Weak or transitional water response.": "استجابة مائية ضعيفة أو انتقالية.",
  "Response compatible with water, mixed water, or wet edges.":
    "استجابة متوافقة مع المياه أو المياه المختلطة أو الحواف الرطبة.",
  "Strong surface-water response.": "استجابة قوية للمياه السطحية.",
  "Very negative BSI value": "قيمة BSI سالبة جداً",
  "Negative BSI value": "قيمة BSI سالبة",
  Transition: "استجابة انتقالية",
  "Probable bare soil": "تربة عارية محتملة",
  "Strong bare-soil / dry signature": "بصمة قوية للتربة العارية أو الجافة",
  "Negative NDBI response": "استجابة سالبة لمؤشر NDBI",
  "Near-zero NDBI response": "استجابة قريبة من الصفر لمؤشر NDBI",
  "Positive NDBI response": "استجابة موجبة لمؤشر NDBI",
  "Strong positive NDBI response": "استجابة موجبة قوية لمؤشر NDBI",
  "Negative SWIR-to-NIR response; this value alone is not a land-cover class.":
    "استجابة سالبة بين SWIR وNIR؛ ولا تمثل هذه القيمة بمفردها فئةً للغطاء الأرضي.",
  "NDBI response close to zero; built-up and bare surfaces may overlap.":
    "استجابة NDBI قريبة من الصفر؛ وقد تتداخل فيها الأسطح المبنية مع التربة العارية.",
  "Positive SWIR-to-NIR response that can occur on built-up or bare surfaces.":
    "استجابة موجبة بين SWIR وNIR قد تظهر فوق الأسطح المبنية أو التربة العارية.",
  "Strong positive SWIR-to-NIR response; interpretation requires supporting data.":
    "استجابة موجبة قوية بين SWIR وNIR؛ ويتطلب تفسيرها بيانات مساندة.",
  "No built-up evidence": "لا توجد دلائل عمرانية",
  "Potential impervious surface or road": "سطح غير منفذ أو طريق محتمل",
  "Built-up area detected": "منطقة مبنية مكتشفة",
  "High-confidence built-up area": "منطقة مبنية بدرجة ثقة عالية",
  "No consistent built-up evidence in the combined observation.":
    "لا توجد دلائل عمرانية متسقة ضمن الرصد المدمج.",
  "Spectral response compatible with roads or other impervious surfaces.":
    "استجابة طيفية متوافقة مع الطرق أو الأسطح الأخرى غير المنفذة.",
  "Built-up evidence identified by temporal or stable land-cover observations.":
    "تم تحديد دلائل عمرانية من خلال الرصد الزمني أو مرجع الغطاء الأرضي المستقر.",
  "Built-up evidence identified by temporal, spectral, or reference observations.":
    "تم تحديد دلائل عمرانية من خلال أرصاد زمنية أو طيفية أو بيانات مرجعية.",
  "Built-up evidence confirmed by multiple independent observations.":
    "تم تأكيد الدلائل العمرانية بواسطة عدة أرصاد مستقلة.",
  "No or very sparse vegetation cover": "غطاء نباتي معدوم أو متناثر جدًا",
  "Bare or non-vegetated surfaces with very sparse vegetation.":
    "أسطح عارية أو غير مغطاة بالنباتات، مع غطاء نباتي متناثر جدًا.",
  "Sparse vegetation cover": "غطاء نباتي متناثر",
  "Sparse or potentially stressed vegetation.": "غطاء نباتي متناثر أو قد يكون متعرضًا للإجهاد.",
  "Moderate vegetation cover": "غطاء نباتي متوسط الكثافة",
  "Moderate vegetation density.": "كثافة نباتية متوسطة.",
  "Dense vegetation cover": "غطاء نباتي كثيف",
  "Dense vegetation cover.": "غطاء نباتي كثيف.",
  "Very dense vegetation cover": "غطاء نباتي شديد الكثافة",
  "Very dense and vigorous vegetation cover.": "غطاء نباتي شديد الكثافة وعالي الحيوية.",
  "Very low": "منخفض جدًا",
  Low: "منخفض",
  Moderate: "متوسط",
  High: "مرتفع",
  "Very high": "مرتفع جدًا",

  "Non-built-up": "مناطق غير مبنية",
  "Vegetation, water, or non-artificial soil.": "غطاء نباتي أو مياه أو تربة غير اصطناعية.",
  "Low artificialization": "تحضر منخفض",
  "Mixed bare soil, roads, or scattered buildings.":
    "مزيج من التربة العارية والطرق أو المباني المتناثرة.",
  "Probable built-up": "عمران محتمل",
  "Likely built-up": "عمران محتمل",
  "Urban signature or impervious surfaces.": "بصمة عمرانية أو أسطح غير منفذة.",
  "Dense built-up": "عمران كثيف",
  "Compact urban or industrial areas.": "مناطق حضرية أو صناعية متراصة.",

  "Dry bare soil / non-water": "تربة عارية جافة / غير مائية",
  "Bare or dry surfaces with no water signal.": "أسطح عارية أو جافة دون إشارة مائية.",
  "Low moisture or vegetation": "رطوبة منخفضة أو غطاء نباتي",
  "Vegetated or lightly moist surfaces with negative NDWI.":
    "أسطح نباتية أو قليلة الرطوبة ذات قيم NDWI سالبة.",
  "Moist vegetation / wet soil": "غطاء نباتي رطب / تربة رطبة",
  "Moist vegetation, wet soil, or banks near water.":
    "غطاء نباتي رطب أو تربة رطبة أو ضفاف مجاورة للمياه.",
  "Shallow or mixed water": "مياه ضحلة أو مختلطة",
  "Mixed water pixels or shallow water response.": "بكسلات مائية مختلطة أو استجابة لمياه ضحلة.",
  "Open water": "مياه مفتوحة",
  "Open water or very strong moisture.": "مياه مفتوحة أو رطوبة شديدة الارتفاع.",

  "Very low bare-soil exposure": "انكشاف منخفض جدًا للتربة العارية",
  "Very limited bare-soil response; surfaces are weakly exposed or largely covered.":
    "استجابة محدودة جدًا للتربة العارية؛ الأسطح قليلة الانكشاف أو مغطاة إلى حد كبير.",
  "Low bare-soil exposure": "انكشاف منخفض للتربة العارية",
  "Low level of soil exposure with partial cover still present.":
    "مستوى منخفض من انكشاف التربة مع استمرار وجود غطاء جزئي.",
  "Moderate bare-soil exposure": "انكشاف متوسط للتربة العارية",
  "Noticeable exposed soil response across mixed or partially uncovered surfaces.":
    "استجابة ملحوظة للتربة المكشوفة في الأسطح المختلطة أو المكشوفة جزئيًا.",
  "High bare-soil exposure": "انكشاف مرتفع للتربة العارية",
  "Strong bare-soil response on clearly exposed dry or sparsely covered land.":
    "استجابة قوية للتربة العارية في الأراضي الجافة المكشوفة بوضوح أو قليلة الغطاء.",
  "Very high bare-soil exposure": "انكشاف مرتفع جدًا للتربة العارية",
  "Very strong bare-soil response on highly exposed, bright, or degraded mineral surfaces.":
    "استجابة شديدة للتربة العارية في الأسطح المعدنية شديدة الانكشاف أو الساطعة أو المتدهورة.",

  "Bare soil or no vegetation": "تربة عارية أو غياب الغطاء النباتي",
  "Bare soil or absent vegetation.": "تربة عارية أو غطاء نباتي غائب.",
  "Very sparse vegetation": "غطاء نباتي متناثر جدًا",
  "Very low vegetation response in a dry context.": "استجابة نباتية منخفضة جدًا في بيئة جافة.",
  "Sparse semi-arid vegetation": "غطاء نباتي شبه جاف متناثر",
  "Sparse vegetation with visible soil influence.":
    "غطاء نباتي متناثر مع تأثير واضح لخلفية التربة.",
  "Moderate vegetation": "غطاء نباتي متوسط",
  "Moderate vegetation cover.": "غطاء نباتي متوسط الكثافة.",
  "High vegetation vigor": "حيوية نباتية مرتفعة",
  "Active vegetation with reduced soil influence.": "غطاء نباتي نشط مع انخفاض تأثير التربة.",
  "Very high vegetation vigor": "حيوية نباتية مرتفعة جدًا",
  "Dense or highly active vegetation.": "غطاء نباتي كثيف أو شديد النشاط.",
  "< 0.10: no / very sparse vegetation": "أقل من 0.10: غطاء نباتي معدوم أو ضعيف جدًا",
  "Bare soil or absent vegetation after soil-background adjustment.":
    "تربة عارية أو غياب الغطاء النباتي بعد تصحيح تأثير خلفية التربة.",
  "0.10–0.25: low vegetation": "0.10–0.25: غطاء نباتي ضعيف",
  "Low vegetation response in a dry or semi-arid context.":
    "استجابة نباتية ضعيفة في بيئة جافة أو شبه جافة.",
  "0.25–0.40: moderate vegetation": "0.25–0.40: غطاء نباتي متوسط",
  "Moderate vegetation cover with reduced soil influence.":
    "غطاء نباتي متوسط مع تقليل تأثير خلفية التربة.",
  "0.40–0.60: dense vegetation": "0.40–0.60: غطاء نباتي كثيف",
  "Dense vegetation cover after soil-background adjustment.":
    "غطاء نباتي كثيف بعد تصحيح تأثير خلفية التربة.",
  ">= 0.60: very dense vegetation": "0.60 فأكثر: غطاء نباتي شديد الكثافة",
  "Very dense or highly active vegetation.": "غطاء نباتي شديد الكثافة أو عالي الحيوية.",
  "No / very sparse vegetation": "غطاء نباتي معدوم أو ضعيف جدًا",

  "Normal water": "مياه طبيعية",
  "Water without a strong dark-slick SAR signal.":
    "مياه دون إشارة رادارية داكنة قوية تدل على بقعة سطحية.",
  "Oil-spill suspect": "اشتباه بانسكاب نفطي",
  "Dark SAR target that passed VV, VH, contrast, angle, water, and connected-pixel filters.":
    "هدف راداري داكن اجتاز عتبات VV وVH والتباين والزاوية والمياه ومرشح البكسلات المتصلة.",
  "Low oil-spill suspicion": "اشتباه منخفض بانسكاب نفطي",
  "Weak dark-target signal that needs context validation.":
    "إشارة ضعيفة لهدف داكن تتطلب التحقق من السياق.",
  "Medium oil-spill suspicion": "اشتباه متوسط بانسكاب نفطي",
  "Dark SAR response with stronger local contrast.": "استجابة رادارية داكنة ذات تباين محلي أقوى.",
  "High oil-spill suspicion": "اشتباه مرتفع بانسكاب نفطي",
  "Strong low-backscatter suspect slick candidate.": "بقعة مشتبه بها ذات تشتت خلفي منخفض وقوي.",
  "Low wind conditions can produce natural dark SAR areas. Oil-spill interpretation has reduced confidence.":
    "قد تُنتج ظروف الرياح الضعيفة مناطق رادارية داكنة طبيعية؛ لذلك تنخفض موثوقية تفسير الاشتباه بالانسكاب النفطي.",
  "OSI-SAR is a dark-target suspect detector over water, not a confirmed oil-spill product.":
    "OSI-SAR كاشف للأهداف الداكنة المشتبه بها فوق المياه، وليس منتجاً يؤكد وجود انسكاب نفطي.",
  "Detection uses one Sentinel-1 IW VV/VH acquisition with VV < -18 dB AND VH < -25 dB AND local contrast >= 2.5 dB.":
    "يستخدم الكشف اكتساباً واحداً من Sentinel-1 بنمط IW وقناتي VV/VH، مع VV أقل من -18 dB وVH أقل من -25 dB وتباين محلي لا يقل عن 2.5 dB.",

  "Strong vegetation loss": "فقدان شديد للغطاء النباتي",
  "Large decrease in vegetation response.": "انخفاض كبير في استجابة الغطاء النباتي.",
  "Moderate vegetation loss": "فقدان متوسط للغطاء النباتي",
  "Moderate decrease in vegetation cover or vigor.": "انخفاض متوسط في الغطاء النباتي أو حيويته.",
  "Stable area": "منطقة مستقرة",
  "Limited NDVI change between periods.": "تغير محدود في NDVI بين الفترتين.",
  "Moderate vegetation gain": "زيادة متوسطة في الغطاء النباتي",
  "Moderate increase in vegetation response.": "زيادة متوسطة في استجابة الغطاء النباتي.",
  "Strong vegetation gain": "زيادة كبيرة في الغطاء النباتي",
  "Large increase in vegetation cover or vigor.": "زيادة كبيرة في الغطاء النباتي أو حيويته.",

  "Water/moisture disappearance": "اختفاء المياه أو الرطوبة",
  "Strong decrease of water or moisture signal.": "انخفاض شديد في إشارة المياه أو الرطوبة.",
  "Moisture decrease": "انخفاض الرطوبة",
  "Moderate decrease of humidity or water response.":
    "انخفاض متوسط في الرطوبة أو الاستجابة المائية.",
  "Limited NDWI change between periods.": "تغير محدود في NDWI بين الفترتين.",
  "Moisture increase": "زيادة الرطوبة",
  "Moderate increase of humidity or water response.":
    "زيادة متوسطة في الرطوبة أو الاستجابة المائية.",
  "Probable water appearance": "ظهور محتمل للمياه",
  "Strong increase suggesting new or expanded water.":
    "زيادة قوية تشير إلى ظهور مياه جديدة أو توسع المسطحات المائية.",

  "Built-up decrease": "انخفاض الاستجابة العمرانية",
  "Strong decrease of built-up spectral response.":
    "انخفاض شديد في الاستجابة الطيفية للمناطق المبنية.",
  "Built-up evidence decreased by two or more classes.":
    "انخفض مستوى الدليل على وجود مناطق مبنية بمقدار فئتين أو أكثر.",
  "Low built-up decrease": "انخفاض عمراني محدود",
  "Moderate decrease of built-up response.": "انخفاض متوسط في استجابة المناطق المبنية.",
  "Built-up evidence decreased by one class.":
    "انخفض مستوى الدليل على وجود مناطق مبنية بمقدار فئة واحدة.",
  "Limited NDBI change between periods.": "تغير محدود في NDBI بين الفترتين.",
  "The built-up evidence class is unchanged.": "لم تتغير فئة الدليل على وجود مناطق مبنية.",
  "Strong NDBI decrease": "انخفاض شديد في استجابة NDBI",
  "Strong decrease of the NDBI spectral response.": "انخفاض شديد في الاستجابة الطيفية لـ NDBI.",
  "Moderate NDBI decrease": "انخفاض متوسط في استجابة NDBI",
  "Moderate decrease of the NDBI response.": "انخفاض متوسط في استجابة NDBI.",
  "Moderate NDBI increase": "زيادة متوسطة في استجابة NDBI",
  "Moderate increase of the NDBI response; bare soil can also raise NDBI.":
    "زيادة متوسطة في استجابة NDBI؛ يمكن للتربة العارية أيضاً رفع NDBI.",
  "Strong NDBI increase": "زيادة شديدة في استجابة NDBI",
  "Strong increase of the NDBI response; not automatically new urbanization.":
    "زيادة شديدة في استجابة NDBI؛ ليست تلقائياً عمراناً جديداً.",
  "New artificialization": "توسع عمراني جديد",
  "Moderate increase of built-up response.": "زيادة متوسطة في استجابة المناطق المبنية.",
  "Built-up evidence increased by one class.":
    "ارتفع مستوى الدليل على وجود مناطق مبنية بمقدار فئة واحدة.",
  "Strong built-up expansion": "توسع عمراني شديد",
  "Strong increase suggesting urban or impervious expansion.":
    "زيادة قوية تشير إلى توسع عمراني أو امتداد الأسطح غير المنفذة.",
  "Built-up evidence increased by two or more classes.":
    "ارتفع مستوى الدليل على وجود مناطق مبنية بمقدار فئتين أو أكثر.",

  "Strong bare-soil decrease": "انخفاض شديد في انكشاف التربة العارية",
  "Strong reduction of exposed bare soil.": "انخفاض شديد في مساحة التربة العارية المكشوفة.",
  "Moderate bare-soil decrease": "انخفاض متوسط في انكشاف التربة العارية",
  "Moderate reduction of bare-soil response.": "انخفاض متوسط في استجابة التربة العارية.",
  "Limited BSI change between periods.": "تغير محدود في BSI بين الفترتين.",
  "Moderate bare-soil increase": "زيادة متوسطة في انكشاف التربة العارية",
  "Moderate increase of exposed soil.": "زيادة متوسطة في التربة المكشوفة.",
  "Strong bare-soil increase": "زيادة شديدة في انكشاف التربة العارية",
  "Strong increase of bare or exposed mineral surface.":
    "زيادة شديدة في الأسطح المعدنية العارية أو المكشوفة.",

  "Strong vegetation-cover loss": "فقدان شديد للغطاء النباتي",
  "Large decrease in SAVI vegetation response.":
    "انخفاض كبير في استجابة الغطاء النباتي وفق مؤشر SAVI.",
  "Moderate vegetation-cover loss": "فقدان متوسط للغطاء النباتي",
  "Moderate vegetation-cover decrease.": "انخفاض متوسط في الغطاء النباتي.",
  "Limited SAVI change between periods.": "تغير محدود في SAVI بين الفترتين.",
  "Low vegetation-cover gain": "زيادة محدودة في الغطاء النباتي",
  "Moderate vegetation-cover gain": "زيادة متوسطة في الغطاء النباتي",
  "Moderate increase in vegetation cover.": "زيادة متوسطة في الغطاء النباتي.",
  "Strong vegetation-cover gain": "زيادة كبيرة في الغطاء النباتي",
  "Strong increase in vegetation cover.": "زيادة كبيرة في الغطاء النباتي.",

  Water: "مياه",
  "Open water or permanent water surfaces.": "مياه مفتوحة أو مسطحات مائية دائمة.",
  "Open water and permanent water surfaces.": "مياه مفتوحة أو مسطحات مائية دائمة.",
  "Natural vegetation": "الغطاء النباتي الطبيعي",
  "Shrubland, grassland, and natural vegetation.": "أراضٍ شجيرية وعشبية وغطاء نباتي طبيعي.",
  Agriculture: "أراضٍ زراعية",
  "Cropland, irrigated parcels, and cultivated areas.": "محاصيل وقطع زراعية مروية ومناطق مزروعة.",
  Forest: "غابات",
  "Tree cover and dense forest vegetation.": "غطاء شجري ونباتات غابية كثيفة.",
  "Built-up": "مناطق مبنية",
  "Urban, industrial, road, and impervious surfaces.": "أسطح حضرية وصناعية وطرق وأسطح غير منفذة.",
  "Bare soil": "تربة عارية",
  "Exposed soil, sand, and mineral surfaces.": "تربة مكشوفة ورمال وأسطح معدنية.",
  Wetlands: "أراضٍ رطبة",
  "Wetlands, marshes, and mixed water vegetation.": "أراضٍ رطبة ومستنقعات وغطاء نباتي مائي مختلط.",
  "Cloud or shadow": "سحب أو ظلال",
  "Cloud, cloud shadow, snow, or no-data samples.": "سحب أو ظلال سحب أو ثلوج أو عينات بلا بيانات.",
  "Dense vegetation / trees": "غطاء نباتي كثيف / أشجار",
  "Tree cover and dense natural vegetation.": "غطاء شجري ونباتات طبيعية كثيفة.",
  "Crops / low vegetation": "محاصيل / غطاء نباتي منخفض",
  "Cropland, grassland, shrubland, or low vegetation.":
    "أراضٍ زراعية أو عشبية أو شجيرية أو غطاء نباتي منخفض.",
  "Built-up area": "منطقة مبنية",
  "Urban, industrial, road, or impervious surfaces.":
    "أسطح حضرية أو صناعية أو طرق أو أسطح غير منفذة.",
  "Bare soil / sand": "تربة عارية / رمال",
  "Exposed soil, sand, desert, or sparse mineral surfaces.":
    "تربة مكشوفة أو رمال أو صحراء أو أسطح معدنية متناثرة.",
  Wetland: "أرض رطبة",
  "Wetland areas when detected by the reference data.":
    "مناطق رطبة عند رصدها في البيانات المرجعية.",
  "Mangrove / specific vegetation": "مانغروف / غطاء نباتي نوعي",
  "Mangrove or specific coastal vegetation where present.":
    "أشجار مانغروف أو غطاء نباتي ساحلي نوعي حيثما وُجد.",
  "Snow / ice": "ثلوج / جليد",
  "Snow or ice where present.": "ثلوج أو جليد حيثما وُجد.",

  "Cluster interpreted from high NDWI and low vegetation response.":
    "مجموعة مفسرة من قيم NDWI مرتفعة واستجابة نباتية منخفضة.",
  "Dense vegetation": "غطاء نباتي كثيف",
  "Cluster interpreted from high NDVI or SAVI.": "مجموعة مفسرة من قيم NDVI أو SAVI مرتفعة.",
  "Cluster interpreted from moderate vegetation response.":
    "مجموعة مفسرة من استجابة نباتية متوسطة.",
  "Cluster interpreted from high built-up spectral response.":
    "مجموعة مفسرة من استجابة طيفية عمرانية مرتفعة.",
  "Cluster interpreted from high bare-soil response and low vegetation.":
    "مجموعة مفسرة من استجابة مرتفعة للتربة العارية وغطاء نباتي منخفض.",
  "Wetland / mixed class": "أرض رطبة / فئة مختلطة",
  "Cluster interpreted from mixed moisture and vegetation response.":
    "مجموعة مفسرة من استجابة مختلطة للرطوبة والغطاء النباتي.",
  "Uninterpreted cluster": "مجموعة غير مفسرة",
  "Cluster without a clear spectral interpretation.": "مجموعة دون تفسير طيفي واضح.",
  "Detailed coverage omitted to speed up processing of the large AOI.":
    "تم تخطي حساب التغطية التفصيلية لتسريع معالجة منطقة الاهتمام الكبيرة.",
  "Detailed coverage deferred to speed up processing of the large AOI.":
    "تم تأجيل حساب التغطية التفصيلية لتسريع معالجة منطقة الاهتمام الكبيرة.",
  "Low Sentinel-2 coverage: widen the period, raise the cloud threshold, or use a median composite.":
    "تغطية Sentinel-2 منخفضة: وسّع الفترة، أو ارفع حد الغيوم، أو استخدم مركّب الوسيط.",
};

const RESULT_LEGEND_EN_ALIASES: Record<string, string> = {
  "Absence ou tres faible couverture vegetale": "No or very sparse vegetation cover",
  "Couverture vegetale faible": "Sparse vegetation cover",
  "Couverture vegetale moyenne": "Moderate vegetation cover",
  "Couverture vegetale forte": "Dense vegetation cover",
  "Couverture vegetale tres forte": "Very dense vegetation cover",
  "Couverture detaillee omise pour accelerer le traitement de la grande AOI.":
    "Detailed coverage omitted to speed up processing of the large AOI.",
  "Couverture detaillee differee pour accelerer le traitement de la grande AOI.":
    "Detailed coverage deferred to speed up processing of the large AOI.",
  "Couverture Sentinel-2 faible: elargir la periode, augmenter le seuil nuages, ou utiliser median composite.":
    "Low Sentinel-2 coverage: widen the period, raise the cloud threshold, or use a median composite.",
  "Sec / non eau": "Dry bare soil / non-water",
  "Humidite faible": "Low moisture or vegetation",
  "Humidite moyenne": "Moist vegetation / wet soil",
  "Eau probable": "Open water",
  "Non bati": "Non-built-up",
  "Faible artificialisation": "Low artificialization",
  "Bati probable": "Likely built-up",
  "Bati dense": "Dense built-up",
  "Moderate loss": "Moderate vegetation-cover loss",
  "Moderate gain": "Moderate vegetation-cover gain",
  "Strong gain": "Strong vegetation-cover gain",
};

export function normalizeResultLegendText(value: unknown): string {
  const text = value == null ? "-" : String(value).trim();
  return RESULT_LEGEND_EN_ALIASES[text] ?? text;
}

export function localizeResultLegendText(value: unknown, language: string): string {
  const normalized = normalizeResultLegendText(value);
  if (language !== "ar") return normalized;

  const translated = RESULT_LEGEND_AR[normalized];
  if (translated) return translated;

  // Backend warnings can concatenate several independently translated
  // sentences. Translate only long phrases here to avoid altering scientific
  // abbreviations, dates, identifiers, or user-defined class names.
  const translatedPhrases = Object.entries(RESULT_LEGEND_AR)
    .filter(([source]) => source.length >= 24 && normalized.includes(source))
    .sort(([left], [right]) => right.length - left.length)
    .reduce((text, [source, target]) => text.replaceAll(source, target), normalized);
  if (translatedPhrases !== normalized) return translatedPhrases;

  const clusterMatch = normalized.match(/^Cluster\s+(\d+)(?:\s*-\s*(.+))?$/i);
  if (clusterMatch) {
    const suffix = clusterMatch[2] ? localizeResultLegendText(clusterMatch[2], language) : "";
    return suffix ? `المجموعة ${clusterMatch[1]} - ${suffix}` : `المجموعة ${clusterMatch[1]}`;
  }

  const classMatch = normalized.match(/^Class\s+(\d+)$/i);
  if (classMatch) return `الفئة ${classMatch[1]}`;
  return normalized;
}
