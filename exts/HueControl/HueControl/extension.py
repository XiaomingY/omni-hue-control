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
from .hue import *

SPACING = 8
# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class HueControlWindow(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    
    def _get_context(self) -> Usd.Stage:
        # Get the UsdContext we are attached to
        return omni.usd.get_context()

    def _build_collapsable_header(self, collapsed, title):
        """Build a custom title of CollapsableFrame"""
        with ui.HStack():
            ui.Label(title, name="collapsable_name")

            if collapsed:
                image_name = "collapsable_opened"
            else:
                image_name = "collapsable_closed"
            ui.Image(name=image_name, width=20, height=20)
    #add light mapping between Omniverse light obect and hue light
    def _addLightGroup(self):
        usd_context = self._get_context()
        stage = usd_context.get_stage()
        if not stage:
            return

        prim_paths = usd_context.get_selection().get_selected_prim_paths()

        if not prim_paths:
            print("Nothing is selected. Please select a light object.")
            return
        #Only one light from selection is used
        prim = stage.GetPrimAtPath(prim_paths[0])

        if prim_paths[0] not in self.lightPrimPath:
            if(UsdLux.Light(prim) and not (prim.IsA(UsdLux.DistantLight)) and not (prim.IsA(UsdLux.DomeLight))):
                self.lightPrimPath.append(prim_paths[0])
                self.create_Window()

    def _removeLightGroup(self, path):
        self.lightPrimPath.remove(path)
        self.mappedHueID.pop(path,None)
        self.originalIntensity.pop(path,None)
        self.create_Window()

    # create ui for a light mapping between Omniverse light obect and hue light
    def create_lightGroup(self, path):
        with ui.CollapsableFrame(path):
            usd_context = self._get_context()
            stage = usd_context.get_stage()
            prim = stage.GetPrimAtPath(path)
            self.originalIntensity[path] = prim.GetAttribute('intensity').Get()
            colorWidgetList = []
            CCTWidgetList = []
            with ui.VStack(height=0, spacing=SPACING, tyle={"margin":1,"padding":5}):
                #button to remove this light group
                ui.Button("-", height = 20, clicked_fn=lambda: self._removeLightGroup(path))
                #Hue ID input
                with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                    ui.Label("Hue ID", width = 50)
                    Id_field = ui.StringField(height = 20)
                #Controls of the light, depends on the hue light functionality, some options could be disabled
                #color control
                with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                    ColorCheckBox = ui.CheckBox(width = 5)
                    ColorCheckBox.model.set_value(False)
                    ui.Label("Color", width = 20)
                    HueGo_color_widget = ui.ColorWidget(1,1,1,width=0, height=0)
                    HueGo_color_model = HueGo_color_widget.model

                    colorWidgetList.append(ColorCheckBox)
                    colorWidgetList.append(HueGo_color_widget)

                    for item in HueGo_color_model.get_item_children():
                        component = HueGo_color_model.get_item_value_model(item)
                        colorDrag = ui.FloatDrag(component,min = 0, max = 1)
                        colorWidgetList.append(colorDrag)
                        #if(Id_field.model.get_value_as_int()):
                        component.add_end_edit_fn(lambda m: control_Color(self.hue,Id_field.model.get_value_as_int(), HueGo_color_model,ColorCheckBox,CCTCheckBox, path))
                # dimming control
                with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                    ui.Label("Intensity", width = 50)
                    Intensity_Slider = ui.IntSlider(step=1, min = 0, max = 100)
                    Intensity_Slider.model.set_value(100)
                # Color temperature control
                with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                    CCTCheckBox = ui.CheckBox(width = 5)
                    CCTCheckBox.model.set_value(True)
                    ui.Label("Color Temperature", width = 20)
                    CCT_Slider = ui.IntSlider(step=100, min = 2200, max = 6500)
                    CCT_Slider.model.set_value(2200)

                CCTWidgetList.append(CCTCheckBox)
                CCTWidgetList.append(CCT_Slider)

        #if Hue ID is defined, use it.
        if(path in self.mappedHueID.keys()):
            Id_field.model.set_value(self.mappedHueID[path])
        #add call backs for UI values changes
        ColorCheckBox.model.add_value_changed_fn(lambda m: changeLightColorMode(m.get_value_as_bool(),ColorCheckBox,CCTCheckBox,path))
        CCTCheckBox.model.add_value_changed_fn(lambda m: changeLightColorMode(not m.get_value_as_bool(),ColorCheckBox,CCTCheckBox,path))
        Id_field.model.add_end_edit_fn(lambda m:self.checkHueLightColorOrCCT(m.get_value_as_int(),colorWidgetList, CCTWidgetList,path))
        Intensity_Slider.model.add_end_edit_fn(lambda m: control_dimming(self.hue, Id_field.model.get_value_as_int(), m.get_value_as_int(), self.originalIntensity[path], path))
        CCT_Slider.model.add_end_edit_fn(lambda m: control_CCT(self.hue, Id_field.model.get_value_as_int(), m.get_value_as_int(),ColorCheckBox,CCTCheckBox, path))
        HueGo_color_widget.model.add_end_edit_fn(lambda m,n: control_Color(self.hue, Id_field.model.get_value_as_int(), m, ColorCheckBox,CCTCheckBox, path))

    def create_Window(self):
        with self._window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(height=0):
                    #hue bridge info for scanning the hue network and find all the lights
                    with ui.CollapsableFrame("Hue Bridge Info"):
                        with ui.VStack(spacing=SPACING, height = 50):
                            with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                                ui.Label("Bridge IP", height = 20, width = 65)
                                IP_field = ui.StringField(height = 20)

                            with ui.HStack(spacing=SPACING, tyle={"margin":1,"padding":5}):
                                ui.Label("User Name", height = 20, width = 65, alignment = ui.Alignment.LEFT_CENTER)
                                username_field = ui.StringField(height = 20, alignment = ui.Alignment.LEFT_CENTER)

                            #Display all lights in the hue network
                            ui.Label("Connected Hue Lights", height = 20, alignment = ui.Alignment.CENTER)
                            self.huelight_field = ui.StringField(height = 150, multiline = True, alignment = ui.Alignment.LEFT_CENTER)
                    
                    with ui.CollapsableFrame("Light Groups"):
                        with ui.VStack(spacing=SPACING,height=0, alignment = ui.Alignment.LEFT_CENTER):
                            #button to add new mapping
                            ui.Button("+", height = 20, clicked_fn=lambda: self._addLightGroup())
                            for i in self.lightPrimPath:
                                self.create_lightGroup(i)

            #if mapping existed, use existing values
            if(self.lights):
                IP_field.model.set_value(self.ip)
                username_field.model.set_value(self.username)
                self.huelight_field.model.set_value(self.hueLightText)
            else:
                IP_field.model.add_value_changed_fn(lambda m: self.set_ip( m.get_value_as_string()))
                username_field.model.add_value_changed_fn(lambda m: self.set_username( m.get_value_as_string()))
                
    def findHueLight(self):
        self.hue = Bridge(self.ip, username=self.username)
        self.lights = self.hue.lights()
        hueLightText = ""
        for i in (n+1 for n in range(len(self.lights))):
            textToPrint = "ID: "+str(i)+": \n    Name: "+str(self.hue['lights'][i]()["name"])+"\n    Product Name: "+str(self.hue['lights'][i]()["productname"])
            hueLightText = hueLightText + textToPrint + "\n"
            print(textToPrint)
            #print(self.lights[1]()["name"])
            #pass
        self.hueLightText = hueLightText
        self.huelight_field.model.set_value(hueLightText)

    #disable some of the UI controls based on available controls of the mapped hue light
    def checkHueLightColorOrCCT(self, unit_Id, coloeWidgetList, cctWidgetList,path):
        self.mappedHueID[path] = unit_Id
        if("colorgamut" not in self.hue['lights'][unit_Id]()['capabilities']['control'].keys()):
            for colorWidget in coloeWidgetList:
                colorWidget.enabled  = False
        if("ct" not in self.hue['lights'][unit_Id]()['capabilities']['control'].keys()):
            for cctWidget in cctWidgetList:
                cctWidget.enabled  = False
    
    def set_ip(self, ip):
        self.ip = ip
        if(self.ip is not None and self.username is not None and len(self.lights)==0):
            self.findHueLight()
            #print(self.lights[1])
    
    def set_username(self, username):
        self.username = username
        if(self.ip is not None and self.username is not None and len(self.lights)==0):
            self.findHueLight()

    def on_startup(self, ext_id):
        print("[omni.hueControl] Hue Control Extension Startup")
        self.ip = None
        self.username = None
        self.hueLightText = ""
        self.hue = None
        self.lights = []
        self.converter = Converter(GamutC)
        self.lightPrimPath = []
        self.originalIntensity = {}
        self.mappedHueID = {}

        self._window = ui.Window("Hue Light Control", width=500, height=450)
        self.create_Window()

    def on_shutdown(self):
        print("[omni.hueControl] Hue Control Extension shutdown")
