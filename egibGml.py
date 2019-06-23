# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EgibGml
                                 A QGIS plugin
 Wtyczka do wczytywania danych Ewidencji Gruntów i Budynków w formacie GML
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-03-25
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Marek Wasilczyk (GIS Support Sp. z o.o.)
        email                : marek.wasilczyk@gis-support.pl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog, QMessageBox
from .resources import *

from .egibGml_dockwidget import EgibGmlDockWidget
import os
import subprocess

from qgis.core import (
    QgsVectorLayer, QgsProject, QgsDataProvider, QgsLayerTreeLayer, Qgis, QgsRelation
)

from osgeo import ogr
import sqlite3


class EgibGml:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'EgibGml_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.dockwidget = EgibGmlDockWidget()
        self.actions = []
        self.menu = self.tr(u'&EGiB GML')
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)
        self.toolbar = self.iface.addToolBar(u'EgibGml')
        self.toolbar.setObjectName(u'EgibGml')

        #Signals handling
        self.dockwidget.fileButton.clicked.connect(self.loadGml)


    def tr(self, message):
        """Get the translation for a string using Qt translation API."""

        return QCoreApplication.translate('EgibGml', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/egibGml/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'EGiB GML'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def loadGml(self):
        gmlFile = QFileDialog.getOpenFileName(None, 'Wybierz plik GML...', filter='*.gml *.xml')[0]
        if not gmlFile:
            return 1
        gmlName = os.path.basename(gmlFile)[:-4]
        gmlNoExt = gmlFile[:-4]

        #Check for existing GFS file
        gfsFile = '%s.gfs' % gmlNoExt
        if os.path.isfile(gfsFile):
            os.rename(gfsFile, '%s_temp.gfs' % gmlNoExt)

        #Convert GML to GeoPackage
        gpkgFile = '%s.gpkg' % gmlNoExt
        createGpkg = True
        if os.path.isfile(gpkgFile):
            result = QMessageBox.question(self.dockwidget, 'Znany plik',
                'Plik GML o podanej nazwie został już wcześniej wczytany. Czy chcesz go przywrócić?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes)
            if result == QMessageBox.Yes:
                createGpkg = False
        if createGpkg:
            conversionParams = [ #Variables necessary for xlink resolution in GMLs
                '--config',
                'GML_ATTRIBUTES_TO_OGR_FIELDS',
                'YES',
                '--config',
                'GML_SKIP_RESOLVE_ELEM', 
                'NONE'
            ]
            try:
                subprocess.check_call(['ogr2ogr', '-f', 'GPKG', gpkgFile, gmlFile, *conversionParams])
            except subprocess.CalledProcessError:
                self.iface.messageBar().pushMessage(
                    'EGiB GML',
                    'Nie udało się wczytać pliku GML. Wystąpił błąd podczas konwersji GML -> GeoPackage',
                    level=Qgis.Critical
                )
                self.cleanAuxFiles(gmlNoExt)
                return 1

        #Add SQL views to database
        conn = sqlite3.connect(gpkgFile)
        c = conn.cursor()
        sqls = [
            '''
            CREATE VIEW UdzialWlasnosciOsobaFizyczna AS
                SELECT udzial.*, osfiz.* FROM EGB_UdzialWlasnosci AS udzial
                JOIN
                (SELECT t1.*, t2.*
                FROM EGB_OsobaFizyczna AS t1
                    LEFT JOIN EGB_Adres AS t2 ON substr(t1.adresOsobyFizycznej_href, instr(t1.adresOsobyFizycznej_href, 'EGiB:')+5)=t2.lokalnyId
                ) AS osfiz
                ON substr(udzial.osobaFizyczna5_href, instr(udzial.osobaFizyczna5_href, 'EGiB:')+5)=osfiz.lokalnyId;
            ''',
            '''
            CREATE VIEW UdzialWlasnosciMalzenstwo AS
                SELECT udzial.*, malzenstwo.* FROM EGB_UdzialWlasnosci AS udzial
                JOIN
                (SELECT t1.*, t2.*, t3.*
                FROM EGB_Malzenstwo AS t1
                    LEFT JOIN EGB_OsobaFizyczna AS t2 ON (substr(t1.osobaFizyczna2_href, instr(t1.osobaFizyczna2_href, 'EGiB:')+5)=t2.lokalnyId
                        OR substr(t1.osobaFizyczna3_href, instr(t1.osobaFizyczna3_href, 'EGiB:')+5)=t2.lokalnyId)
                    LEFT JOIN EGB_Adres AS t3 ON substr(t2.adresOsobyFizycznej_href, instr(t2.adresOsobyFizycznej_href, 'EGiB:')+5)=t3.lokalnyId
                ) AS malzenstwo
                ON substr(udzial.malzenstwo4_href, instr(udzial.malzenstwo4_href, 'EGiB:')+5)=malzenstwo.lokalnyId;
            ''',
            '''
            CREATE VIEW UdzialWlasnosciInstytucja AS
                SELECT udzial.*, instytucja.* FROM EGB_UdzialWlasnosci AS udzial
                JOIN
                (SELECT t1.*, t2.*
                FROM EGB_Instytucja AS t1
                    LEFT JOIN EGB_Adres AS t2 ON substr(t1.adresInstytucji_href, instr(t1.adresInstytucji_href, 'EGiB:')+5)=t2.lokalnyId
                ) AS instytucja
                ON substr(udzial.instytucja3_href, instr(udzial.instytucja3_href, 'EGiB:')+5)=instytucja.lokalnyId;
            ''',
            '''
            CREATE VIEW UdzialWlasnosciGrupowy AS
                SELECT udzial.*, grupowy.* FROM EGB_UdzialWlasnosci AS udzial
                JOIN
                (SELECT t1.*, t2.*, t3.*
                FROM EGB_PodmiotGrupowy AS t1
                    LEFT JOIN EGB_OsobaFizyczna AS t2 ON substr(t1.osobaFizyczna4_href, instr(t1.osobaFizyczna4_href, 'EGiB:')+5)=t2.lokalnyId
                    LEFT JOIN EGB_Adres AS t3 ON substr(t1.adresPodmiotuGrupowego_href, instr(t1.adresPodmiotuGrupowego_href, 'EGiB:')+5)=t3.lokalnyId
                ) AS grupowy
                ON substr(udzial.podmiotGrupowy1_href, instr(udzial.podmiotGrupowy1_href, 'EGiB:')+5)=grupowy.lokalnyId;
            ''',
            # Add above views to geopackage
            '''
            INSERT INTO gpkg_contents (table_name, identifier, data_type) VALUES ( 'UdzialWlasnosciGrupowy', 'UdzialWlasnosciGrupowy', 'attributes');
            ''',
            '''
            INSERT INTO gpkg_contents (table_name, identifier, data_type) VALUES ( 'UdzialWlasnosciMalzenstwo', 'UdzialWlasnosciMalzenstwo', 'attributes');
            ''',
            '''
            INSERT INTO gpkg_contents (table_name, identifier, data_type) VALUES ( 'UdzialWlasnosciInstytucja', 'UdzialWlasnosciInstytucja', 'attributes');
            ''',
            '''
            INSERT INTO gpkg_contents (table_name, identifier, data_type) VALUES ( 'UdzialWlasnosciOsobaFizyczna', 'UdzialWlasnosciOsobaFizyczna', 'attributes');
            '''
        ]
        for sql in sqls:
            try:
                errorMsg = ''
                c.execute(sql)
            except sqlite3.OperationalError as error:
                errorMsg = str(error) if 'already exists' not in str(error) else None
            except sqlite3.IntegrityError as error:
                errorMsg = str(error) if str(error) != 'UNIQUE constraint failed: gpkg_contents.identifier' else None
            finally:
                if errorMsg:
                    self.iface.messageBar().pushMessage(
                        'EGiB GML',
                        'Wystąpił błąd podczas tworzenia warstw pomocniczych: %s.' % errorMsg,
                        level=Qgis.Critical
                    )
                    self.cleanAuxFiles(gmlNoExt)
                    return 1
        conn.commit()
        conn.close()

        projInst = QgsProject.instance()

        #Add map layers
        root = projInst.layerTreeRoot()
        gmlGroup = root.addGroup(gmlName)
        gmlLayers = QgsVectorLayer(gpkgFile, gmlName, 'ogr')
        for layer in gmlLayers.dataProvider().subLayers():
            layerName = layer.split(QgsDataProvider.SUBLAYER_SEPARATOR)[1]
            vlayer = QgsVectorLayer('{}|layername={}'.format(
                gpkgFile,
                layerName
            ), layerName, 'ogr')
            gmlGroup.insertChildNode(1,QgsLayerTreeLayer(vlayer))
            projInst.addMapLayer(vlayer, False)
        self.cleanAuxFiles(gmlNoExt)

        #Add QGIS project relations between layers of GPKG
        addedRelations = [
            self.createRelation(projInst, 'EGB_DzialkaEwidencyjna', 'UdzialWlasnosciOsobaFizyczna', 'JRG2_href', 'JRG_href'),
            self.createRelation(projInst, 'EGB_DzialkaEwidencyjna', 'UdzialWlasnosciMalzenstwo', 'JRG2_href', 'JRG_href'),
            self.createRelation(projInst, 'EGB_DzialkaEwidencyjna', 'UdzialWlasnosciInstytucja', 'JRG2_href', 'JRG_href'),
            self.createRelation(projInst, 'EGB_DzialkaEwidencyjna', 'UdzialWlasnosciGrupowy', 'JRG2_href', 'JRG_href')
        ]
        for rel in addedRelations:
            if not rel.isValid():
                self.iface.messageBar().pushMessage(
                    'EGiB GML',
                    'Wystąpił błąd podczas tworzenia relacji %s.' % rel.name(),
                    level=Qgis.Critical
                )
                return 1

        self.iface.messageBar().pushMessage(
            'EGiB GML',
            'Pomyślnie dodano warstwę GML.',
            level=Qgis.Success
        )
        self.dockwidget.filePathLabel.setText(os.path.basename(gmlFile))
        self.dockwidget.filePathLabel.setToolTip(gmlFile)


    def createRelation(self, project, parentLayer, childLayer, pk, fk):
        """ Creates and adds a QGIS relation for given layers and matching fields """

        relManager = project.relationManager()
        newRelation = QgsRelation()
        newRelation.setReferencedLayer(str(project.mapLayersByName(parentLayer)[0].id()))
        newRelation.setReferencingLayer(str(project.mapLayersByName(childLayer)[0].id()))
        newRelation.addFieldPair(fk, pk)
        relationId = parentLayer[:10] + '_' + childLayer
        newRelation.setName(relationId)
        newRelation.setId(relationId)
        relManager.addRelation(newRelation)

        return newRelation


    def cleanAuxFiles(self, gmlNoExt):
        """ Removes auxiliary import files """

        gfsFile = '%s.gfs' % gmlNoExt
        try:
            os.remove(gfsFile)
            os.remove('%s.resolved.gml' % gmlNoExt)
        except FileNotFoundError:
            pass
        try:
            os.rename('%s_temp.gfs' % gmlNoExt, gfsFile)
        except FileNotFoundError:
            pass


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&EGiB GML'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        self.dockwidget.show()
