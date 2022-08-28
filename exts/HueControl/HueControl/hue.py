import omni.ext
import omni.ui as ui
import omni.kit.commands
from pxr import Usd
from pxr import UsdLux
from pxr import Sdf, Gf
import numpy as np
omni.kit.pipapi.install("qhue")
omni.kit.pipapi.install("rgbxy")
omni.kit.pipapi.install("colour-science")
import colour
from qhue import Bridge
from rgbxy import Converter
from rgbxy import GamutC



#change light control mode, color temperature control or color control
def changeLightColorMode(ColorBoolean, ColorCheckBox, CCTCheckBox, primpath):
        omni.kit.commands.execute('ChangeProperty',
            prop_path=Sdf.Path(primpath+'.enableColorTemperature'),
            value= not ColorBoolean,
            prev=None)
        if(ColorBoolean):
            ColorCheckBox.model.set_value(True)
            CCTCheckBox.model.set_value(False)
        else:
            ColorCheckBox.model.set_value(False)
            CCTCheckBox.model.set_value(True)
            

def CCT2Mired(CCT):
    return int(1000000/CCT)

def control_dimming(hue, unit_Id, level, originalOmniIntensity, primpath):
    #print("Change dimming "+str(unit_Id)+" "+str(level))
    if not hue["lights"][unit_Id]()["state"]["on"]:
        hue.lights[unit_Id].state(on = True)

    hue.lights[unit_Id].state(bri=int(level*255/100))
    #if(unit_Id==1):
    omni.kit.commands.execute('ChangeProperty',
        prop_path=Sdf.Path(primpath+'.intensity'),
        value=originalOmniIntensity*level/100,
        prev=originalOmniIntensity)

def control_CCT(hue, unit_Id, level, ColorCheckBox, CCTCheckBox, primpath): 
    #print("Change CCT "+str(unit_Id)+" "+str(level))
    if not hue["lights"][unit_Id]()["state"]["on"]:
        hue.lights[unit_Id].state(on = True)
    if("ct" in hue['lights'][unit_Id]()['capabilities']['control'].keys()):
        hue.lights[unit_Id].state(ct=CCT2Mired(level))
        if("colorgamut" in hue['lights'][unit_Id]().keys()):
            omni.kit.commands.execute('ChangeProperty',
                prop_path=Sdf.Path(primpath+'.colorTemperature'),
                value=level,
                prev=6500)
        else:
            changeLightColorMode(False, ColorCheckBox, CCTCheckBox, primpath)
            omni.kit.commands.execute('ChangeProperty',
                prop_path=Sdf.Path(primpath+'.colorTemperature'),
                value=level,
                prev=6500)
            omni.kit.commands.execute('ChangeProperty',
            prop_path=Sdf.Path(primpath+'.color'),
            value=Gf.Vec3f(1, 1, 1),
            prev=Gf.Vec3f(1, 1, 1))

def colour_srgb_to_xy(R,G,B):
    RGB = np.array([R,G,B])
    XYZ = colour.sRGB_to_XYZ(RGB) 
    xyY = colour.XYZ_to_xyY(XYZ)
    return(xyY[0],xyY[1])

def control_Color(hue, unit_Id, widget_colorModel, ColorCheckBox, CCTCheckBox, primpath):
    print("Change Color ")
    if not hue["lights"][unit_Id]()["state"]["on"]:
        hue.lights[unit_Id].state(on = True)
    changeLightColorMode(True, ColorCheckBox, CCTCheckBox, primpath)
    components = widget_colorModel.get_item_children()
    R = widget_colorModel.get_item_value_model(components[0]).get_value_as_float()
    G = widget_colorModel.get_item_value_model(components[1]).get_value_as_float()
    B = widget_colorModel.get_item_value_model(components[2]).get_value_as_float()
    #hue.lights[unit_Id].state(xy=converter.rgb_to_xy(R, G, B))
    hue.lights[unit_Id].state(xy=colour_srgb_to_xy(R/255, G/255, B/255))

    omni.kit.commands.execute('ChangeProperty',
	            prop_path=Sdf.Path(primpath+'.color'),
	            value=Gf.Vec3f(R, G, B),
	            prev=Gf.Vec3f(1, 1, 1))