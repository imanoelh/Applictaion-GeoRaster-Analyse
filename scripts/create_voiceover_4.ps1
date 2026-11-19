$ErrorActionPreference = 'Stop'
$sourceRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10'
$outputRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10'
$video = Join-Path $sourceRoot '4.mp4'
$audio = Join-Path $outputRoot '4_georaster_classification_voiceover.wav'
$output = Join-Path $outputRoot '4_georaster_classification_explained.mp4'
$text = @'
This is the GeoRaster classification workflow.

I start in Map and Analysis with a Sentinel-2 image selected and the study area visible on the map. The image and the area of interest provide the data for the classification.

In the Raster analysis panel, I open the classification tools. The workflow guides me through creating training samples. I select the sample type, keep the training split active, and choose the drawing tool.

I then click on the map to add representative sample points or polygons. Each sample describes a land-cover class, such as natural vegetation, built-up area, bare soil, or water. The map keeps the samples inside the selected study area so they can be reviewed before running the analysis.

When the training samples are ready, I continue to the next step and review the sample list. GeoRaster shows the number of samples and the assigned class for each one. I can go back, add another sample, or proceed when the sample set is sufficient.

The classification process then analyses the image values and groups or labels pixels according to the selected workflow. The output is rendered directly on the map with a colour for each class.

The result panel summarises the detected clusters or classes, their areas, percentages, and representative colours. The legend makes the classification easy to read: built-up surfaces, soil, vegetation, water, and other classes are separated visually.

I can inspect the result over the original map, check the class statistics, and export the classified raster or the associated report and data files.

The complete GeoRaster sequence is: select the image, define the study area, create and review training samples, run the classification, inspect the map and class statistics, and export the result.
'@
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female, [System.Speech.Synthesis.VoiceAge]::Adult, 0, [System.Globalization.CultureInfo]::GetCultureInfo('en-US'))
$synth.Rate = -1; $synth.Volume = 100; $synth.SetOutputToWaveFile($audio); $synth.Speak($text); $synth.Dispose()
$ffmpeg = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
& $ffmpeg -y -i $video -i $audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -af apad -t 300.0 $output
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
Write-Output "VOICEOVER=$audio"; Write-Output "VIDEO=$output"
