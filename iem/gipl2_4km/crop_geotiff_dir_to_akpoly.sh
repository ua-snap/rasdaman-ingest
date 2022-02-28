cd input_data/Permafrost/geotiff
for i in `find . -type f -name "*.tif"`; do gdalwarp -crop_to_cutline -cutline ../clipper_shp/iem_aleutians_bounding_box.shp -dstnodata -9999.0 -overwrite -t_srs EPSG:3338 -co COMPRESS=LZW $i "cropped"${i:1}; done
