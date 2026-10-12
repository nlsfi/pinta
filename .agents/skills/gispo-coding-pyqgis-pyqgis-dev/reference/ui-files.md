# Qt Designer .ui files

A `.ui` file is XML that describes a widget tree. `uic` turns it into PyQt calls at load
time (`uic.loadUiType`, `uic.loadUi`) or at build time (`pyuic5`, `pyuic6`). Reading the
XML directly is fine. The tools below tell you what it means and whether it works.

## Structure

```xml
<ui version="4.0">
 <class>MyDialog</class>                         <!-- name of the generated Ui_ class -->
 <widget class="QDialog" name="MyDialog">       <!-- root widget; class = Qt, QGIS or own widget -->
  <property name="windowTitle"><string>Title</string></property>
  <layout class="QVBoxLayout" name="verticalLayout">
   <item><widget class="QLineEdit" name="name_edit"/></item>
   <item row="0" column="1"> ... </item>         <!-- grid layouts add row/column/rowspan/colspan -->
   <item><spacer name="spacer"><property name="orientation"><enum>Qt::Vertical</enum></property></spacer></item>
  </layout>
 </widget>
 <customwidgets> ... </customwidgets>            <!-- non-Qt classes used above -->
 <resources><include location="resources.qrc"/></resources>
 <connections> ... </connections>                <!-- signal/slot links made in Designer -->
 <tabstops><tabstop>name_edit</tabstop></tabstops>
 <buttongroups/>
</ui>
```

Property value types: `<string>`, `<bool>`, `<number>`, `<double>`,
`<enum>Qt::AlignLeft</enum>`, `<set>Qt::AlignLeft|Qt::AlignVCenter</set>`, `<rect>`,
`<size>`, `<sizepolicy hsizetype=".." vsizetype="..">`, `<font>`, `<iconset>`, `<color>`,
`<cursorShape>`, `<stringlist>`, `<date>`, `<url>`. Custom Q_PROPERTY values of QGIS
widgets look the same, for example
`<property name="filters"><set>QgsMapLayerProxyModel::VectorLayer</set></property>`.

Every `name="..."` becomes an attribute on the loaded widget: `self.name_edit`.

## Custom widgets

`<customwidgets>` tells uic which Python class to build for a non-Qt `class="..."`:

```xml
<customwidget>
 <class>QgsFilterLineEdit</class>
 <extends>QLineEdit</extends>
 <header>qgsfilterlineedit.h</header>            <!-- QGIS widget: the C++ header name -->
</customwidget>
<customwidget>
 <class>CodeComboBox</class>
 <extends>QComboBox</extends>
 <header>my_plugin.gui.code_combobox</header>    <!-- own widget: dotted Python module path -->
</customwidget>
```

- QGIS widgets with a `qgs*.h` header are mapped to `qgis.gui` classes by the uic widget
  plugin that QGIS installs (`python/custom_widgets/qgis_customwidgets.py` in the source).
  Loading through `qgis.PyQt.uic` makes this work for every `QgsXxx` widget in `qgis.gui`.
- Own widgets need a dotted module path in `<header>` (a trailing `.h` is stripped) that is
  importable when the file loads. The class name must match `<class>`. That module must
  not touch `iface` at import time.
- Own widgets must accept the parent: `def __init__(self, parent=None, ...)` with
  `super().__init__(parent)`. PyQt6 uic calls `Class(parent=parent)` (keyword); PyQt5 uic
  calls `Class(parent)` (positional). A constructor whose first parameter is something else
  gets the parent in that parameter on Qt 5 and raises `unexpected keyword argument 'parent'`
  on Qt 6. `check_ui.py` under `$QGIS4_PYTHON` catches this at load.
- `<extends>` should be the real Qt base class. Designer uses it to know which properties
  to show.

## Loading in plugin code

```python
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "dialog.ui"))

class MyDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)      # creates self.<name> for every named widget
```

`uic.loadUi(path, self)` does the same in one step. Both read the XML at run time, so
there is no build step. `pyuic` output is for reading, or for projects that commit
generated code.

## Tools (all in this skill's `scripts/`)

- See the generated code: `"$QGIS_PYTHON" -m PyQt5.uic.pyuic file.ui` (with the Qt 6 Python: `-m PyQt6.uic.pyuic`).
- Check compile and load: `"$QGIS_PYTHON" check_ui.py file.ui`, then again with `$QGIS4_PYTHON`. A directory argument checks every `.ui` under it.
- See it: `"$QGIS_PYTHON" render_ui.py file.ui --names`, then Read the PNG. `--names` fills empty labels, buttons and group boxes with their objectName, so you can map picture to XML.
- Edit visually: Qt Designer with the QGIS widgets is `qgis-designer.bat` (OSGeo4W: `C:\OSGeo4W\bin\qgis-designer.bat`) or `designer` in the QGIS install.

## Where the format is defined

- `$QTBASE_SRC/src/tools/uic/ui4.h` lists every element and attribute (`DomWidget`, `DomProperty`, ...).
- `PyQt5/uic/uiparser.py` and `PyQt5/uic/properties.py` next to the PyQt5 package of `$QGIS_PYTHON` show how PyQt reads each tag and property type.
- `https://doc.qt.io/qt-5/designer-ui-file-format.html` is the same in prose.

## Rules when editing the XML by hand

- Keep Qt 5 spelling for enums (`Qt::AlignLeft`, not `Qt::AlignmentFlag::AlignLeft`) so both uic versions load the file.
- Every widget needs a unique `name`. Names become attributes; use snake_case that matches the code.
- Put widgets inside `<layout>` / `<item>`. A widget outside a layout gets a fixed geometry.
- List every non-Qt class in `<customwidgets>`, once. Without an entry uic fails with an unknown-widget error.
- `<resources>` needs the compiled `*_rc.py` module at load time. If the plugin sets icons in code, keep `<resources/>` empty.
- After each edit run `check_ui.py` under both Pythons, then `render_ui.py`.
