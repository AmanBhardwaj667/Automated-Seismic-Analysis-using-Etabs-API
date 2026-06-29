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

## Seismic Design Parameters (IS 1893:2016)

| Parameter | Value | Reason / Reference |
|-----------|-------|--------------------|
| Seismic Zone | Zone IV | Uttarakhand falls under Zone IV as per IS 1893:2016 seismic classification |
| Zone Factor (Z) | 0.24 | IS 1893:2016 Table 3 / Zone IV value |
| Soil Type | Type II (Medium Soil) | Pantnagar/Tarai region consists mainly of alluvial deposits |
| Importance Factor (I) | 1.0 | Normal residential/office building category |
| Response Reduction Factor (R) | 5.0 | Special RC Moment Resisting Frame (SMRF) |
| Damping Ratio | 5% | Standard damping value for RC structures |
| Analysis Method | Equivalent Static / Response Spectrum (Sa/g) | As per IS 1893:2016 seismic design procedure |
| Design Code | IS 1893:2016 | Current Indian standard for earthquake resistant design |
