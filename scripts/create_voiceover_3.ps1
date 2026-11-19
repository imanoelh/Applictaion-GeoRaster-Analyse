$ErrorActionPreference = 'Stop'
$sourceRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10'
$outputRoot = 'D:\Personel\TASK\WebGIS Raster Aanalyse\Protoype WebGIS Raster Analyse\Georaster-19-10\Georaster-19-10'
$video = Join-Path $sourceRoot '3.mp4'
$audio = Join-Path $outputRoot '3_georaster_change_detection_voiceover.wav'
$output = Join-Path $outputRoot '3_georaster_change_detection_explained.mp4'
$text = @'
This is the GeoRaster water and change analysis workflow.

I begin in Map and Analysis with the selected Sentinel-2 image and the area of interest already visible on the map.

In the Raster analysis panel, I select NDWI, the Normalized Difference Water Index. GeoRaster explains that NDWI is used to highlight water surfaces and separate water from surrounding land.

I click Run raster analysis. The result is calculated for the selected image and displayed immediately inside the study area. The map uses a colour scale, and the legend explains the water-related classes shown on the overlay.

The results panel reports the main values for the raster, including the minimum, maximum, median, valid pixels, and area coverage. The histogram helps me understand how the index values are distributed across the selected area.

I can then switch to Change Detection. I choose the change-detection analysis and define the comparison periods. GeoRaster compares the selected raster information between the two periods and highlights the areas where the index has changed.

The change result is shown as a map overlay, with its own legend and statistics. This makes it possible to identify changes in water-related conditions and inspect them directly in the geographic context.

Finally, I use the export controls to create a GeoTIFF, map image, CSV, or PDF report. The report keeps the selected area, analysis type, statistics, and visual result together.

The complete sequence is simple: choose the image, select NDWI or Change Detection, run the calculation, review the map and statistics, and export the GeoRaster result.
'@
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female, [System.Speech.Synthesis.VoiceAge]::Adult, 0, [System.Globalization.CultureInfo]::GetCultureInfo('en-US'))
$synth.Rate = -1; $synth.Volume = 100; $synth.SetOutputToWaveFile($audio); $synth.Speak($text); $synth.Dispose()
$ffmpeg = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
& $ffmpeg -y -i $video -i $audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -af apad -t 169.57 $output
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed with exit code $LASTEXITCODE" }
Write-Output "VOICEOVER=$audio"; Write-Output "VIDEO=$output"
