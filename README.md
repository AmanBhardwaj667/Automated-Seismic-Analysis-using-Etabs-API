# Automated-Seismic-Analysis-using-Etabs-API

requirements.txt
Install with: pip install -r requirements.txt
IMPORTANT: Use 32-bit Python 3.9 (x86)

comtypes==1.2.0
numpy==1.24.4
pandas==2.0.3
scipy==1.11.4
openpyxl==3.1.2
XlsxWriter==3.1.9
matplotlib==3.7.4
tqdm==4.66.1

## Seismic Design Parameters

| Parameter | Value | Reason / Reference |
|---|---|---|
| Seismic Zone | IV | Uttarakhand falls under Zone IV as per IS 1893:2016 |
| Zone Factor (Z) | 0.24 | IS 1893:2016 seismic zone factor for Zone IV |
| Soil Type | Type II (Medium) | Pantnagar lies in the Tarai region with alluvial/medium soil conditions |
| Importance Factor (I) | 1.0 | Residential/office building category |
| Response Reduction Factor (R) | 5.0 | Special RC Moment Resisting Frame (SMRF) |
| Damping Ratio | 5% | Standard damping value for reinforced concrete structures |
| Analysis Method | Sa/g Method (Response Spectrum) | As per IS 1893:2016 seismic analysis procedure |
| Design Code | IS 1893:2016 | Current Indian standard for earthquake-resistant design |
