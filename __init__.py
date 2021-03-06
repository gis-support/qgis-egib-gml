# -*- coding: utf-8 -*-
"""
/***************************************************************************
 EgibGml
                                 A QGIS plugin
 Wtyczka do wczytywania danych Ewidencji Gruntów i Budynków w formacie GML
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2019-03-25
        copyright            : (C) 2019 by Marek Wasilczyk (GIS Support Sp. z o.o.)
        email                : marek.wasilczyk@gis-support.pl
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load EgibGml class from file EgibGml.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .egibGml import EgibGml
    return EgibGml(iface)
