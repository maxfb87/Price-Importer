import bpy
import csv
import textwrap
import blenderbim.tool as tool
from pathlib import Path
from ifcopenshell.api.cost.data import Data
from blenderbim.bim.ifc import IfcStore

my_columns_enum = []
PriceData = {}
price_exists = False

def _label_multiline(context, text, parent):
    chars = int(context.region.width / 7)   # 7 pix on 1 character
    wrapper = textwrap.TextWrapper(width=chars)
    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)


class _PT_PriceImporter(bpy.types.Panel):
    bl_label = "Price Importer"
    bl_idname = "N-PANEL_PT_Price Importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Price Importer"

    def draw(self, context):
        global PriceData
        global price_exists
        global csv_file
        global csv_reader
        
        layout = self.layout
        scene = context.scene
        props = context.scene.price_importer_properties
        
        #my_csv_file = "/home/max/prezzario.csv"
        #codice = "A.04.03.a"
        
        row = layout.row(align = True)
        row.prop(props, "my_csv_file_path")
        row.operator(ImportFile.bl_idname, icon = "FILE_FOLDER", text = "")
        
        if props.my_csv_file_path == "":
            row = layout.row()
            row.label(text = "Please insert the csv file path")
            return
        
        file_path = Path(str(props.my_csv_file_path))
        if not file_path.exists():
            row = layout.row()
            row.label(text = "File doesn't exist")
            return
        
        row = layout.row()
        row.prop(props, "my_identification")
        
        row = layout.row()
        row.prop(props, "my_name")
        
        row = layout.row()
        row.prop(props, "my_cost_value")
        
        row = layout.row()
        row.separator()
     
        row = layout.row(align = True)
        row.prop(props, "my_column")
        
        row = layout.row(align = True)
        row.prop(props, "my_searching_value")
        row.operator(SearchPrice.bl_idname, text = "", icon = "VIEWZOOM")
        
        if props.my_searching_value == "":
            row = layout.row()
            row.label(text = "Please insert the searching value")
            return

        if not price_exists:
            row = layout.row()
            row.label(text = "Searching field is not present")
            return
        
        if not PriceData:
            return
        
        row = layout.row()
        row.label(text = "Codice:")
        row.label(text = PriceData[props.my_identification])
        
        row = layout.row()
        row.label(text = "Descrizione:")

        _label_multiline(
             context = context,
             text = PriceData[props.my_name],
             parent = layout,
        )
        
        row = layout.row()
        row.label(text = "Unità di misura:")
        row.label(text = PriceData["UMI"])
        row = layout.row()
        row.label(text = "Prezzo:")
        row.label(text = PriceData[props.my_cost_value])
        
        self.layout.operator(ImportPrice.bl_idname, text = "Import price", icon = "IMPORT")
        
        
        
        #cost_props = context.scene.BIMCostProperties
        
        #row = layout.row()
        #row.prop(props, "my_price_status")
        #row = layout.row()
        #row.label(text = str(cost_props.cost_items[cost_props.active_cost_item_index].identification))
        #row = layout.row()
        #row.label(text = str(cost_props.cost_items[cost_props.active_cost_item_index].name))
        #row = layout.row()
        #row.label(text = str(cost_props.cost_item_resources[cost_props.active_cost_item_index].total_quantity))

class SearchPrice(bpy.types.Operator):
    bl_idname = "object.search_price"
    bl_label = "Import Price"
    
    def execute(self, context):
        global PriceData, price_exists
        props = context.scene.price_importer_properties
        with open(props.my_csv_file_path, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            PriceData = {}
            price_exists = False
            for row in csv_reader:
                if row[props.my_column] == props.my_searching_value:
                    PriceData = row
                    PriceData[props.my_cost_value] = PriceData[props.my_cost_value].replace(",", "")
                    price_exists = True
                        
        return {"FINISHED"}

def UpdateMySearchingValue(self, context):
    SearchPrice.execute(self, context)

def GetIfcQuantityFromUMI(UMI):
    quantities = {
        "m²" : "IfcQuantityArea",
        "n" : "IfcQuantityCount",
        "m" : "IfcQuantityLength",
        "h" : "IfcQuantityTime",
        "m³" : "IfcQuantityVolume",
        "kg" : "IfcQuantityWeight",
        }
    
    if UMI in quantities.keys():
        return quantities[UMI]
    else:
        return
        
class ImportPrice(bpy.types.Operator):
    bl_idname = "object.import_price"
    bl_label = "Import Price"
    
    def execute(self, context):
        global PriceData
        ifc = tool.Ifc()
        file = tool.Ifc().get()
        props = context.scene.price_importer_properties
        cost_props = context.scene.BIMCostProperties
        
        cost_item_ifcid = file.by_id(cost_props.cost_items[cost_props.active_cost_item_index].ifc_definition_id)
        
        cost_props.cost_items[cost_props.active_cost_item_index].identification = PriceData[props.my_identification]
        cost_props.cost_items[cost_props.active_cost_item_index].name = PriceData[props.my_name]

        ifc_quantity_class = GetIfcQuantityFromUMI(PriceData["UMI"])
        
        if ifc_quantity_class:
            ifc.run("cost.add_cost_item_quantity",
                cost_item = cost_item_ifcid,
                ifc_class = ifc_quantity_class,
                )
        else:
            print("Didn't found measure unit, sorry")
        
        attributes = {"AppliedValue" : float(PriceData[props.my_cost_value][:-2])}
        value = ifc.run("cost.add_cost_value", parent = cost_item_ifcid)
        
        ifc.run("cost.edit_cost_value", cost_value = value, attributes = attributes)
        
        Data.load(file)
        
        props.my_price_status = "Importato"
        return {'FINISHED'}

class ImportFile(bpy.types.Operator):
    bl_idname = "object.import_csv_file"
    bl_label = "Import the CSV file"
    bl_options = {"REGISTER", "UNDO"}
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        context.scene.price_importer_properties.my_csv_file_path = self.filepath
        return {"FINISHED"}
        
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

def purge():
    global my_columns_enum
    my_columns_enum = []

def my_column_items(self, context):
    props = bpy.context.scene.price_importer_properties
    global my_columns_enum
    my_columns_enum = []
    if props.my_csv_file_path:
        with open(props.my_csv_file_path, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            columns = csv_reader.fieldnames
            id=0
            for column in columns:
                my_columns_enum.append((column, column, "", id)) #{('NAME', 'NAME', 'DESCR', 'ID')}
                id+=1
    return my_columns_enum

class PriceImporterProperties(bpy.types.PropertyGroup):
    my_csv_file_path: bpy.props.StringProperty(name="CSV data", default ="")
    my_searching_value: bpy.props.StringProperty(name="Searching value", default ="", update = UpdateMySearchingValue)
    my_price_status: bpy.props.StringProperty(name="my_price_status", default ="Non importato")
    my_column: bpy.props.EnumProperty(name="Searching column", items = my_column_items)
    my_identification: bpy.props.EnumProperty(name="Identification field", items = my_column_items)
    my_name: bpy.props.EnumProperty(name="Name field", items = my_column_items)
    my_cost_value: bpy.props.EnumProperty(name="Cost value field", items = my_column_items)

def register():
    bpy.utils.register_class(_PT_PriceImporter)
    bpy.utils.register_class(PriceImporterProperties)
    bpy.types.Scene.price_importer_properties = bpy.props.PointerProperty(type=PriceImporterProperties)
    bpy.utils.register_class(ImportPrice)
    bpy.utils.register_class(ImportFile)
    bpy.utils.register_class(SearchPrice)
    #bpy.utils.register_class(UpdateMySearchingValue)

def unregister():
    bpy.utils.unregister_class(_PT_PriceImporter)
    bpy.utils.unregister_class(PriceImporterProperties)
    bpy.utils.unregister_class(ImportPrice)
    bpy.utils.unregister_class(ImportFile)
    bpy.utils.unregister_class(SearchPrice)
    #bpy.utils.unregister_class(UpdateMySearchingValue)

if __name__ == "__main__":
    register()
