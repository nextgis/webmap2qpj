#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import requests
import pyproj
import argparse
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET

#python webmap2qpj.py --url demo --login administrator --password 123456 --webmap_id 752

parser = argparse.ArgumentParser()
parser.add_argument('--url',type=str,required=True)
parser.add_argument('--login',type=str,required=True,default='administrator')
parser.add_argument('--password',type=str,required=True)
parser.add_argument('--webmap_id',type=str,required=True)

args = parser.parse_args()

def generate_project(webmap_id, url, login, password):
    AUTH = HTTPBasicAuth(login, password)
    #Чтение веб-карты как json
    r = requests.get('http://' + url + '.nextgis.com/api/resource/%s' % (webmap_id,), auth = AUTH)
    r.encoding = 'utf-8'
    t = r.json()

    #Экстенты карты
    extent_top = t['webmap']['extent_top']
    extent_bottom = t['webmap']['extent_bottom']
    extent_left = t['webmap']['extent_left']
    extent_right = t['webmap']['extent_right']

    #Перевод координат экстента в прямоугольные
    p1 = pyproj.Proj(init='epsg:4326')
    p2 = pyproj.Proj(init='epsg:3857')
    x2, y2 = pyproj.transform(p1,p2,extent_left, extent_bottom)  #сначала долгота, потом широта
    xmin = x2
    ymin = y2
    x3, y3 = pyproj.transform(p1,p2,extent_right, extent_top) #сначала долгота, потом широта
    xmax = x3
    ymax = y3
    #print(x2, y2)

    #К стилям карты
    styles = t['webmap']['root_item']['children']
    length = len(styles)
    basemaps = t['basemap_webmap']['basemaps']

    parent_list = []
    style_list = []
    table_names = []
    display_name = []
    geometry_type = []
    cls = []
    rows = []
    datasource = []
    webnames = []
    url_webmap = []

    #Создание списков id стилей и слоев карты
    for d in range(length):
        style_id = styles[d]['layer_style_id']
        st_id = "http://" + login + ':' + password + '@' + url + ".nextgis.com/api/resource/%i/qml" % (style_id)
        style_list.append(st_id)
        r1 = requests.get('http://' + url + '.nextgis.com/api/resource/%i' % (style_id,), auth = AUTH)
        q = r1.json()
        parent_id = q['resource']['parent']['id']
        par_id = "http://" + login + ':' + password + '@' + url + ".nextgis.com/api/resource/%i/geojson" % (parent_id)
        parent_list.append(par_id)
        r2 = requests.get('http://' + url + '.nextgis.com/api/resource/%i' % (parent_id,), auth = AUTH)
        s = r2.json()
        cl = s['resource']['cls']
        cls.append(cl)
        
        if cl == 'postgis_layer':
            table_name = s['postgis_layer']['table']
            table_names.append(table_name)
            postgis_id = s['postgis_layer']['connection']['id']
            r3 = requests.get('http://' + '.nextgis.com/api/resource/%i' % (postgis_id,), auth = AUTH)
            d = r3.json()
            dic = d['postgis_connection']
            dic['dbname'] = dic['database']
            del dic['database']
            dic['host'] = dic['hostname']
            del dic['hostname']
            dic['user'] = dic['username']
            del dic['username']
            dis_name = s['resource']['display_name']
            display_name.append(dis_name)
            geom_type = s['vector_layer']['geometry_type']
            geometry_type.append(geom_type)
            
            r2 = requests.get('http://' + url + '.nextgis.com/api/resource/%i' % (parent_id,), auth = AUTH)
            s = r2.json()
            dis_name = s['resource']['display_name']
            display_name.append(dis_name)
            geom_type = s['postgis_layer']['geometry_type']
            geometry_type.append(geom_type)
            cl = s['resource']['cls']
            cls.append(cl)

            row = 'dbname=' + "'" + dic['dbname'] + "'" + ' host=' + dic['host'] + ' port=5432 user=' + "'" + dic['user'] + "'" + " sslmode=disable key='ogc_fid' srid=3857 type=" + geom_type + ' table=' + "'" + table_name + "'" + ' (wkb_geometry) sql='
            rows.append(row)
            #print(row)

            ds = 'dbname=' + "'" + dic['dbname'] + "'" + ' host=' + dic['host'] + ' port=5432 user=' + "'" + dic['user'] + "'" + ' password=' + "'" + dic['password'] + "'" + " sslmode=disable key='ogc_fid' srid=3857 type=" + geom_type + ' table=' + "'" + table_name + "'" + ' (wkb_geometry) sql='
            datasource.append(ds)
            #print(ds)

            
        elif cl == 'vector_layer':
            dis_name = s['resource']['display_name']
            display_name.append(dis_name)
            geom_type = s['vector_layer']['geometry_type']
            geometry_type.append(geom_type)
            
    #Подключение к шаблону проекта, заполнение
    tree = ET.parse('D:/NextGIS/Webmap_to_project/test1.qgs')
    root = tree.getroot()
            
    for rank in root.iter('layer-tree-group'):
        for f in range(len(parent_list)):
            if cl == 'postgis_layer':
                co = ET.Element("layer-tree-layer", expanded="1", providerKey="postgres", checked="Qt::Checked", id = table_names[f] + str(f), source=str(rows[f]), name=table_names[f])
            elif cl == 'vector_layer':
                co = ET.Element("layer-tree-layer", expanded="1", providerKey="ogr", checked="Qt::Checked", id = display_name[f] + str(f), source = parent_list[f], name = display_name[f])
            cs = ET.SubElement(co, 'customproperties')
            rank.append(co)
            
    co = root[3]

    wroot = ET.Element('layer-tree-group', expanded="1", checked="Qt::Checked", attrib = {'mutually-exclusive':"1", 'mutually-exclusive-child':"0"}, name="Basemaps")
    if basemaps == []:
        ce = ET.Element('layer-tree-layer', expanded="1", providerKey="wms", checked="Qt::Checked", id="OpenStreetMap_Standard_aka_Mapnik", source="type=xyz&amp;zmin=0&amp;zmax=19&amp;url=http://tile.openstreetmap.org/{z}/{x}/{y}.png", name="OpenStreetMap Standard aka Mapnik")
        cs = ET.SubElement(ce, 'customproperties')
        wroot.append(ce)
    else:
        for basemap in basemaps:
            resource_id = basemap['resource_id']
            r3 = requests.get('http://' + url + '.nextgis.com/api/resource/%i' % (resource_id,), auth = AUTH)
            g = r3.json()
            map_name = g['resource']['display_name']
            webnames.append(map_name)
            urlmap = g['basemap_layer']['url']
            url_webmap.append(urlmap)
            ce = ET.Element('layer-tree-layer', expanded="1", providerKey="wms", checked="Qt::Checked", id=map_name + 1, source="type=xyz&amp;zmin=0&amp;zmax=19&amp;%s" %(urlmap), name=map_name)
            cs = ET.SubElement(ce, 'customproperties')
            wroot.append(ce)
    co.append(wroot)
    elems = root.findall(".//xmin")
    for elem in elems:
        elem.text = str(xmin)
    elems = root.findall(".//xmax")
    for elem in elems:
        elem.text = str(xmax)
    elems = root.findall(".//ymin")
    for elem in elems:
        elem.text = str(ymin)
    elems = root.findall(".//ymax")
    for elem in elems:
        elem.text = str(ymax) 
        
    for rank in root.iter('custom-order'):
        for f in range(len(style_list)):
            co = ET.Element("item")
            rank.append(co)
    elems = root.findall(".//item")
    f = 0
    for elem in elems:
        if cl == 'postgis_layer':
            elem.text = table_names[f] + str(f)
        elif cl == 'vector_layer':
            elem.text = display_name[f] + str(f)
        f += 1
        
    for rank in root.iter('custom-order'):
        if basemaps == []:
            co = ET.Element("item")
            co.text = 'OpenStreetMap_Standard_aka_Mapnik'
    else:
        for name in webnames:
            co = ET.Element("item")
            co.text = name + 1
        
    for rank in root.iter('legend'):
        for f in range(len(parent_list)):
            if cl == 'postgis_layer':
                co = ET.Element("legendlayer", checked="Qt::Checked", drawingOrder ="-1", name=table_names[f], open="true", showFeatureCount="0")
            elif cl == 'vector_layer':
                co = ET.Element("legendlayer", checked="Qt::Checked", drawingOrder ="-1", name=display_name[f], open="true", showFeatureCount="0")
            ce = ET.Element("filegroup", hidden="false", open="true")
            cs = ET.SubElement(ce, "legendlayerfile", isInOverview = "0", layerid = str(f), visible = "1")
            co.append(ce)
            rank.append(co)
    co = root[7]
    if basemaps == []:
        wroot = ET.Element('legendlayer', drawingOrder="-1", open="true", checked="Qt::Checked", name="OpenStreetMap Standard aka Mapnik", showFeatureCount="0")
        ce = ET.Element("filegroup", hidden="false", open="true")
        cs = ET.SubElement(ce, "legendlayerfile", isInOverview = "0", layerid = 'OpenStreetMap_Standard_aka_Mapnik', visible = "1")
        wroot.append(ce)
        co.append(wroot)
    else:
        for f in range(len(webnames)):
            wroot = ET.Element('legendlayer', drawingOrder="-1", open="true", checked="Qt::Checked", name=webnames[f], showFeatureCount="0")
            ce = ET.Element("filegroup", hidden="false", open="true")
            cs = ET.SubElement(ce, "legendlayerfile", isInOverview = "0", layerid = webnames[f], visible = "1")
            wroot.append(ce)
            co.append(wroot)
    #Запись данных о слоях        
    for rank in root.iter('projectlayers'):
        for f in range(len(parent_list)):
            co = ET.Element("maplayer", geometry = geometry_type[f], hasScaleBasedVisibilityFlag="0", maxLabelScale="1e+08", maximumScale="1e+08", minLabelScale="0", minimumScale="0", readOnly="0", scaleBasedLabelVisibilityFlag="0", simplifyAlgorithm="0", simplifyDrawingHints="0", simplifyDrawingTol="1", simplifyLocal="1", simplifyMaxScale="1", type="vector") 
            ce = ET.Element("extent")
            #print(cs)
            cs1 = ET.SubElement(ce, "xmin")
            cs1.text = str(xmin)
            cs2 = ET.SubElement(ce, "ymin")
            cs2.text = str(ymin)
            cs3 = ET.SubElement(ce, "xmax")
            cs3.text = str(xmax)
            cs4 = ET.SubElement(ce, "ymax")
            cs4.text = str(ymax)
            co.append(ce)
            if cl == 'postgis_layer':
                ce1 = ET.Element('id')
                ce1.text = table_names[f] + str(f)
                co.append(ce1)
                ce2 = ET.Element('datasource')
                ce2.text = datasource[f]
                co.append(ce2)
                ce3 = ET.Element('keywordList')
                cs3 = ET.SubElement(ce3, 'value')
                co.append(ce3)
                ce4 = ET.Element('layername')
                ce4.text = table_names[f]
                co.append(ce4)
                ce5 = ET.Element('srs')
                cs5 = ET.SubElement(ce5, 'spatialrefsys')
                css1 = ET.SubElement(cs5, 'proj4')
                css1.text = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
                css2 = ET.SubElement(cs5, 'srsid')
                css2.text = str(3857)
                css3 = ET.SubElement(cs5, 'srid')
                css3.text = str(3857)
                css4 = ET.SubElement(cs5, 'authid')
                css4.text = 'EPSG:3857'
                css5 = ET.SubElement(cs5, 'description')
                css5.text = 'WGS 84 / Pseudo Mercator'
                css6 = ET.SubElement(cs5, 'projectionacronym')
                css6.text = 'merc'
                css7 = ET.SubElement(cs5, 'ellipsoidacronym')
                css7.text = 'WGS84'
                css8 = ET.SubElement(cs5, 'geographicflag')
                css8.text = 'false'
                co.append(ce5)
                ce6 = ET.Element('provider', encoding="UTF-8")
                ce6.text = 'postgres'
                co.append(ce6)
            elif cl == 'vector_layer':
                ce1 = ET.Element('id')
                ce1.text = display_name[f] + str(f)
                co.append(ce1)
                ce2 = ET.Element('datasource')
                ce2.text = parent_list[f]
                co.append(ce2)
                ce3 = ET.Element('keywordList')
                cs3 = ET.SubElement(ce3, 'value')
                co.append(ce3)
                ce4 = ET.Element('layername')
                ce4.text = display_name[f]
                co.append(ce4)
                ce5 = ET.Element('srs')
                cs5 = ET.SubElement(ce5, 'spatialrefsys')
                css1 = ET.SubElement(cs5, 'proj4')
                css1.text = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
                css2 = ET.SubElement(cs5, 'srsid')
                css2.text = str(3857)
                css3 = ET.SubElement(cs5, 'srid')
                css3.text = str(3857)
                css4 = ET.SubElement(cs5, 'authid')
                css4.text = 'EPSG:3857'
                css5 = ET.SubElement(cs5, 'description')
                css5.text = 'WGS 84 / Pseudo Mercator'
                css6 = ET.SubElement(cs5, 'projectionacronym')
                css6.text = 'merc'
                css7 = ET.SubElement(cs5, 'ellipsoidacronym')
                css7.text = 'WGS84'
                css8 = ET.SubElement(cs5, 'geographicflag')
                css8.text = 'false'
                co.append(ce5)
                ce6 = ET.Element('provider', encoding="UTF-8")
                ce6.text = 'ogr'
                co.append(ce6)
            ce7 = ET.Element('vectorjoins')
            co.append(ce7)
            ce8 = ET.Element('layerDependencies')
            co.append(ce8)
            ce9 = ET.Element('expressionfields')
            co.append(ce9)
            ce10 = ET.Element('map-layer-style-manager', current="")
            cs10 = ET.SubElement(ce10, 'map-layer-style', name="")
            co.append(ce10)        
            
            #Копирование свойств стиля с qml
            r = requests.get(style_list[f], auth = AUTH)
            t = r.text
            root = ET.fromstring(t)
            edittypes_tag = root.find('edittypes')
            renderer_tag = root.find('renderer-v2')
            labeling_tag = root.find('labeling')
            customproperties_tag = root.find('customproperties')
            blendMode_tag = root.find('blendMode')
            featureBlendMode_tag = root.find('featureBlendMode')
            layerTransparency_tag = root.find('layerTransparency')
            displayfield_tag = root.find('displayfield')
            label_tag = root.find('label')
            labelattributes_tag = root.find('labelattributes')
            SingleCategoryDiagramRenderer_tag = root.find('SingleCategoryDiagramRenderer')
            DiagramLayerSettings_tag = root.find('DiagramLayerSettings')
            annotationform_tag = root.find('annotationform')
            aliases_tag = root.find('aliases')
            excludeAttributesWMS_tag = root.find('excludeAttributesWMS')
            excludeAttributesWFS_tag = root.find('excludeAttributesWFS')
            attributeactions_tag = root.find('attributeactions')
            attributetableconfig_tag = root.find('attributetableconfig')
            editform_tag = root.find('editform')
            editforminit_tag = root.find('editforminit')
            editforminitcodesource_tag = root.find('editforminitcodesource')
            editforminitfilepath_tag = root.find('editforminitfilepath')
            editforminitcode_tag = root.find('editforminitcode')
            featformsuppress_tag = root.find('featformsuppress')
            editorlayout_tag = root.find('editorlayout')
            widgets_tag = root.find('widgets')
            conditionalstyles_tag = root.find('conditionalstyles')
            defaults_tag = root.find('defaults')
            previewExpression_tag = root.find('previewExpression')
            co.append(edittypes_tag)
            co.append(renderer_tag)
            co.append(labeling_tag)
            co.append(customproperties_tag)
            co.append(blendMode_tag)
            co.append(featureBlendMode_tag)
            co.append(layerTransparency_tag)
            co.append(displayfield_tag)
            co.append(label_tag)
            co.append(labelattributes_tag)
            co.append(SingleCategoryDiagramRenderer_tag)
            co.append(DiagramLayerSettings_tag)
            co.append(annotationform_tag)
            co.append(aliases_tag)
            co.append(excludeAttributesWMS_tag)
            co.append(excludeAttributesWFS_tag)
            co.append(attributeactions_tag)
            co.append(attributetableconfig_tag)
            co.append(editform_tag)
            co.append(editforminit_tag)
            co.append(editforminitcodesource_tag)
            co.append(editforminitfilepath_tag)
            co.append(editforminitcode_tag)
            co.append(featformsuppress_tag)
            co.append(editorlayout_tag)
            co.append(widgets_tag)
            co.append(conditionalstyles_tag)
            co.append(defaults_tag)
            co.append(previewExpression_tag)
            rank.append(co)

    #Запись данных о подложках        
    elem = root[8]
    if basemaps == []:
        co = ET.Element("maplayer", minimumScale="0", maximumScale="1e+08", type="raster", hasScaleBasedVisibilityFlag="0") 
        ce = ET.Element("extent")
        #print(cs)
        cs1 = ET.SubElement(ce, "xmin")
        cs1.text = '-20037508.34278924390673637'
        cs2 = ET.SubElement(ce, "ymin")
        cs2.text = '-20037508.34278925508260727'
        cs3 = ET.SubElement(ce, "xmax")
        cs3.text = '20037508.34278924390673637'
        cs4 = ET.SubElement(ce, "ymax")
        cs4.text = '20037508.34278924390673637'
        co.append(ce)
        ce1 = ET.Element('id')
        ce1.text = 'OpenStreetMap_Standard_aka_Mapnik'
        co.append(ce1)
        ce2 = ET.Element('datasource')
        ce2.text = 'type=xyz&zmin=0&zmax=19&url=http://tile.openstreetmap.org/{z}/{x}/{y}.png'
        co.append(ce2)
        ce3 = ET.Element('keywordList')
        cs3 = ET.SubElement(ce3, 'value')
        co.append(ce3)
        ce4 = ET.Element('attribution', href="https://www.openstreetmap.org/copyright")
        ce4.text = 'OpenStreetMap contributors, CC-BY-SA'
        co.append(ce4)
        ce5 = ET.Element('layername')
        ce5.text = 'OpenStreetMap Standard aka Mapnik'
        co.append(ce5)
        ce6 = ET.Element('srs')
        cs6 = ET.SubElement(ce6, 'spatialrefsys')
        css1 = ET.SubElement(cs6, 'proj4')
        css1.text = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
        css2 = ET.SubElement(cs6, 'srsid')
        css2.text = str(3857)
        css3 = ET.SubElement(cs6, 'srid')
        css3.text = str(3857)
        css4 = ET.SubElement(cs6, 'authid')
        css4.text = 'EPSG:3857'
        css5 = ET.SubElement(cs6, 'description')
        css5.text = 'WGS 84 / Pseudo Mercator'
        css6 = ET.SubElement(cs6, 'projectionacronym')
        css6.text = 'merc'
        css7 = ET.SubElement(cs6, 'ellipsoidacronym')
        css7.text = 'WGS84'
        css8 = ET.SubElement(cs6, 'geographicflag')
        css8.text = 'false'
        co.append(ce6)
        ce7 = ET.Element('customproperties')
        cs7 = ET.SubElement(ce7, 'property', key="identify/format", value="Undefined")
        co.append(ce7)
        ce8 = ET.Element('provider')
        ce8.text = 'wms'
        co.append(ce8)
        ce9 = ET.Element('noData')
        cs9 = ET.SubElement(ce9, 'noDataList', bandNo="1", useSrcNoData="0")
        co.append(ce9)
        ce10 = ET.Element('map-layer-style-manager', current = "")
        cs10 = ET.SubElement(ce10, 'map-layer-style', name="")
        co.append(ce10)
        ce11 = ET.Element('pipe')
        css1 = ET.SubElement(ce11, 'rasterrenderer', opacity="1", alphaBand="-1", band="1", type="singlebandcolordata")
        cs11 = ET.SubElement(css1, 'rasterTransparency')
        css2 = ET.SubElement(ce11, 'brightnesscontrast', brightness="0", contrast="0")
        css3 = ET.SubElement(ce11, 'huesaturation', colorizeGreen="128", colorizeOn="0", colorizeRed="255", colorizeBlue="128", grayscaleMode="0", saturation="0", colorizeStrength="100")
        css4 = ET.SubElement(ce11, 'rasterresampler', maxOversampling="2")
        co.append(ce11)
        ce12 = ET.Element('blendMode')
        ce12.text = '0'
        co.append(ce12)
        elem.append(co)
    else:
        for f in range(len(webnames)):
            co = ET.Element("maplayer", minimumScale="0", maximumScale="1e+08", type="raster", hasScaleBasedVisibilityFlag="0") 
            ce = ET.Element("extent")
            cs1 = ET.SubElement(ce, "xmin")
            cs1.text = '-20037508.34278924390673637'
            cs2 = ET.SubElement(ce, "ymin")
            cs2.text = '-20037508.34278925508260727'
            cs3 = ET.SubElement(ce, "xmax")
            cs3.text = '20037508.34278924390673637'
            cs4 = ET.SubElement(ce, "ymax")
            cs4.text = '20037508.34278924390673637'
            co.append(ce)
            co = ET.Element("maplayer", minimumScale="0", maximumScale="1e+08", type="raster", hasScaleBasedVisibilityFlag="0") 
            ce = ET.Element("extent")
            cs1 = ET.SubElement(ce, "xmin")
            cs1.text = str(xmin)
            cs2 = ET.SubElement(ce, "ymin")
            cs2.text = str(ymin)
            cs3 = ET.SubElement(ce, "xmax")
            cs3.text = str(xmax)
            cs4 = ET.SubElement(ce, "ymax")
            cs4.text = str(ymax)
            co.append(ce)
            ce1 = ET.Element('id')
            ce1.text = webnames[f] + 1
            co.append(ce1)
            ce2 = ET.Element('datasource')
            ce2.text = 'type=xyz&zmin=0&zmax=19&url=' + url_webmap[f]
            co.append(ce2)
            ce3 = ET.Element('keywordList')
            cs3 = ET.SubElement(ce3, 'value')
            co.append(ce3)
            copyright = g['basemap_layer']['copyright_text']
            copyright_url = g['basemap_layer']['copyright_url']
            ce4 = ET.Element('attribution', href = copyright_url)
            ce4.text = str(copyright)
            co.append(ce4)
            ce5 = ET.Element('layername')
            ce5.text = webnames[f]
            co.append(ce5)
            ce6 = ET.Element('srs')
            cs6 = ET.SubElement(ce6, 'spatialrefsys')
            css1 = ET.SubElement(cs6, 'proj4')
            css1.text = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext  +no_defs'
            css2 = ET.SubElement(cs6, 'srsid')
            css2.text = str(3857)
            css3 = ET.SubElement(cs6, 'srid')
            css3.text = str(3857)
            css4 = ET.SubElement(cs6, 'authid')
            css4.text = 'EPSG:3857'
            css5 = ET.SubElement(cs6, 'description')
            css5.text = 'WGS 84 / Pseudo Mercator'
            css6 = ET.SubElement(cs6, 'projectionacronym')
            css6.text = 'merc'
            css7 = ET.SubElement(cs6, 'ellipsoidacronym')
            css7.text = 'WGS84'
            css8 = ET.SubElement(cs6, 'geographicflag')
            css8.text = 'false'
            co.append(ce6)
            ce7 = ET.Element('customproperties')
            cs7 = ET.SubElement(ce7, 'property', key="identify/format", value="Undefined")
            co.append(ce7)
            ce8 = ET.Element('provider')
            ce8.text = 'wms'
            co.append(ce8)
            ce9 = ET.Element('noData')
            cs9 = ET.SubElement(ce9, 'noDataList', bandNo="1", useSrcNoData="0")
            co.append(ce9)
            ce10 = ET.Element('map-layer-style-manager', current = "")
            cs10 = ET.SubElement(ce10, 'map-layer-style', name="")
            co.append(ce10)
            ce11 = ET.Element('pipe')
            css1 = ET.SubElement(ce11, 'rasterrenderer', opacity="1", alphaBand="-1", band="1", type="singlebandcolordata")
            cs11 = ET.SubElement(css1, 'rasterTransparency')
            css2 = ET.SubElement(ce11, 'brightnesscontrast', brightness="0", contrast="0")
            css3 = ET.SubElement(ce11, 'huesaturation', colorizeGreen="128", colorizeOn="0", colorizeRed="255", colorizeBlue="128", grayscaleMode="0", saturation="0", colorizeStrength="100")
            css4 = ET.SubElement(ce11, 'rasterresampler', maxOversampling="2")
            co.append(ce11)
            ce12 = ET.Element('blendMode')
            ce12.text = '0'
            co.append(ce12)
            elem.append(co)
                
                
    #Запись в новый проект
    tree.write('D:/NextGIS/Webmap_to_project/project_test5.qgs')

    #Добавление строки Doctype
    my_file = open('D:/NextGIS/Webmap_to_project/project_test5.qgs', "r")
    lines_of_file = my_file.readlines()
    my_file.close()
    my_file = open('D:/NextGIS/Webmap_to_project/project_test5.qgs', "w")
    lines_of_file.insert(0, "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>")
    my_file.writelines(lines_of_file)
    my_file.close()

if __name__ == '__main__':
    generate_project(args.webmap_id, args.url, args.login, args.password)
