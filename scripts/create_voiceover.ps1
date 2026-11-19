$ErrorActionPreference = 'Stop'

$sourceRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10'
$outputRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10'
$video = Join-Path $sourceRoot '1.mp4'
$audio = Join-Path $outputRoot '1_georaster_building_detection_voiceover.wav'
$output = Join-Path $outputRoot '1_georaster_building_detection_explained.mp4'

$text = @'
This is the GeoRaster building detection workflow.

I start in Map and Analysis and open the AI Object Detection panel. Here I choose the Buildings function.

First, I select Local orthophoto as the source. Then I click Upload GeoTIFF and choose the RGB orthophoto used for the analysis. GeoRaster checks that the file is georeferenced and compatible with the building workflow.

Next, I select the building model from the Building model list. I keep the probability threshold at the value shown in the panel, or adjust it when a different level of detection is needed.

When the settings are ready, I click Run Building detection. GeoRaster prepares the image, divides it into tiles, and runs the selected model on each tile.

The model produces a building probability map. GeoRaster merges the tile results, applies the detection threshold, and converts the result into building polygons.

The detected buildings are then displayed on the map as an overlay on the orthophoto. This makes it possible to check the position and shape of every detected footprint directly in GeoRaster.

The result panel provides the main statistics, including the number of candidates, total area, average area, and perimeter information.

Finally, I can export the result as GeoJSON, CSV, metadata JSON, or a ZIP package. The same polygons remain available in the map for visual inspection.

This is the complete GeoRaster sequence: choose the source, upload the orthophoto, select the building model, run detection, review the polygons and statistics, and export the result.
'@

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female, [System.Speech.Synthesis.VoiceAge]::Adult, 0, [System.Globalization.CultureInfo]::GetCultureInfo('en-US'))
$synth.Rate = -1
$synth.Volume = 100
$synth.SetOutputToWaveFile($audio)
$synth.Speak($text)
$synth.Dispose()

$ffmpeg = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
& $ffmpeg -y -i $video -i $audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -af apad -t 180.16 $output
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
Write-Output "VOICEOVER=$audio"
Write-Output "VIDEO=$output"
