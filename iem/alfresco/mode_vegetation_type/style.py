style_name = "climate_impact_reports"
abstract = "Style for Climate Impact Reports vegetation mode minimaps."
query_type = "None"
color_table_type = "SLD"

color_table_definition = <StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:gml="http://www.opengis.net/gml" xmlns:ogc="http://www.opengis.net/ogc" xmlns:sld="http://www.opengis.net/sld" version="1.0.0">
  <UserLayer>
    <sld:LayerFeatureConstraints>
      <sld:FeatureTypeConstraint />
    </sld:LayerFeatureConstraints>
    <sld:UserStyle>
      <sld:Name>alfresco_vegetation_type_mode_statistic5</sld:Name>
      <sld:FeatureTypeStyle>
        <sld:Rule>
          <sld:RasterSymbolizer>
            <sld:ChannelSelection>
              <sld:GrayChannel>
                <sld:SourceChannelName>1</sld:SourceChannelName>
              </sld:GrayChannel>
            </sld:ChannelSelection>
            <sld:ColorMap type="values">
              <sld:ColorMapEntry quantity="-9999" color="#FFFFFF" label="-9999" />
              <sld:ColorMapEntry quantity="0" color="#ffffff" label="0.0000" />
              <sld:ColorMapEntry quantity="1" color="#1f78b4" label="1.0000" />
              <sld:ColorMapEntry quantity="2" color="#b2df8a" label="2.0000" />
              <sld:ColorMapEntry quantity="3" color="#33a02c" label="3.0000" />
              <sld:ColorMapEntry quantity="4" color="#fb9a99" label="4.0000" />
              <sld:ColorMapEntry quantity="5" color="#e31a1c" label="5.0000" />
              <sld:ColorMapEntry quantity="6" color="#fdbf6f" label="6.0000" />
              <sld:ColorMapEntry quantity="7" color="#ff7f00" label="7.0000" />
              <sld:ColorMapEntry quantity="8" color="#cab2d6" label="8.0000" />
            </sld:ColorMap>
          </sld:RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </UserLayer>
</StyledLayerDescriptor>
