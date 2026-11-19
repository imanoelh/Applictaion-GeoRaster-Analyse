$ErrorActionPreference = 'Stop'
$sourceRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10'
$outputRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10'
$video = Join-Path $sourceRoot '2.mp4'
$audio = Join-Path $outputRoot '2_georaster_raster_analysis_voiceover.wav'
$output = Join-Path $outputRoot '2_georaster_raster_analysis_explained.mp4'

$text = @'
This is the GeoRaster raster analysis workflow.

I start in Map and Analysis, where the map and the analysis panel are visible together. The map shows the working area, while the panel controls the image search and the raster calculations.

First, I choose the start date and end date for the analysis period. Then I select the satellite sensor, in this case Sentinel-2, and choose the analysis resolution.

Next, I draw the area of interest directly on the map. GeoRaster uses this rectangle to search for imagery and to limit the calculations to the selected study area.

After the search, the available images appear in the results list. I select the image that matches the area and time period I want to analyse.

The analysis panel then provides the available raster products. I can choose an index such as NDVI for vegetation, NDWI for water, NDBI for built-up areas, BSI for bare soil, or SAVI for vegetation with soil adjustment.

When I select an index, GeoRaster displays its description and the Run raster analysis button. I click Run raster analysis to calculate the selected product for the current image and area of interest.

The result is rendered directly on the map with a colour scale and legend. The panel also shows the result statistics, including the valid pixel count, minimum and maximum values, average value, and coverage information.

I can switch between the available raster results, inspect the legend, and compare the layers with the original map. The result can then be exported for further GIS work.

This is the complete GeoRaster sequence: define the dates, choose Sentinel-2, draw the AOI, select an image, choose an index, run the analysis, inspect the map and statistics, and export the raster result.
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
& $ffmpeg -y -i $video -i $audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -af apad -t 204.57 $output
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
Write-Output "VOICEOVER=$audio"
Write-Output "VIDEO=$output"
