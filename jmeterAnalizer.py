##/usr/bin/python
## coding=UTF-8

"""
Copyright (C) 2008  Jose Pablo Sarco and Santiago Suarez Ordoñez

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software Foundation,
   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

For contacting the authors:
Jose Pablo Sarco: sarcojp  at  hotmail  dot  com
Santiago Suarez Ordoñez: santiycr  at  gmail  dot  com
"""

import csv
import os, time, math
import xml.etree.cElementTree as ET
from matplotlib import pyplot
import matplotlib
import numpy.numarray as na
#import psyco  
#psyco.full()  

#Options Parsing
from optparse import OptionParser
parser = OptionParser()
parser.add_option("-i", "--input" , dest="input",
                  help="La ruta al output generado por jmeter", 
                  metavar="INPUTFILE", default="Results.jtl")
parser.add_option("-o", "--output", dest="output", 
                  default="JMeterReport.html",
                  help="El nombre del archivo generado")

(options, args) = parser.parse_args()

# Statistic functions used in the report
def avg(seq):
    return sum(seq)/float(len(seq))

def stdev(seq):
    if len(seq) < 1: 
        return None
    elif len(seq) == 1:
        return 0
    else:
        avge = avg(seq)
        sdsq = sum([(i - avge) ** 2 for i in seq])
        stdev = (sdsq / float((len(seq) - 1)) ** .5)
        return stdev

def percentile(seq, percent):
    if len(seq) < 1: 
        value = None
    elif (percent >= 100):
        sys.stderr.write('ERROR: percentile must be < 100.  you supplied: %s\n'% percentile)
        value = None
    else:
        element_idx = int(len(seq) * (percent / 100.0))
        seq.sort()
        value = seq[element_idx]
    return value

def uniq (iterable):
    r = []
    for i in iterable:
        if i not in r: r.append(i)
    return r


class Report:
    
    """ This class is used to load the csv and generate all the report
    sections
    
    It's instantiated sending the csvinput and then it has different functions
    that process the data and create the section in the final html. Once the report
    has all the desired sections, you should use the generate function sendign the
    desired output file"""
    
    def __init__(self, csvinput):
        
        # First, we load the user's configuration if the xml file is found.
        self.config = {}
        
        try:
            xml = ET.parse("config.xml").getroot() 
        except IOError:
            
            # If the file is not found, we use the defaults and ask for the
            # controls
            print "Configuration file not found, using defaults"

            #General
            self.config['descripcionrep'] = u"Descripción del reporte"
            self.config['descripcionproy'] = u"Descripción del proyecto"
            
            #Response time
            self.config['respTime_satisfactorio'] = 10000 
            self.config['respTime_tolerante'] = 13000
            self.config['respTime_percentile'] = 90
            
            #Alerts
            self.config['alertas_elapsedporc'] = 0.2
            self.config['alertas_latencyporc'] = 0.2
            
            #APDEX
#            self.config['apdex_satisfactorio'] = 10000 
#            self.config['apdex_tolerante'] = 11000
            
            #Throughput
            self.config['throughput_satisfactorio'] = 10000 
            self.config['throughput_tolerante'] = 11000
            self.config['throughput_percentile'] = 90

        except SyntaxError:
            print "Configuration file found, loading data..."
            print "The syntax in the configuration file is not correct, please correct the file or delete it to use the default configuration."
            os._exit(15)
        else:
            print "Configuration file found, loading data..."
            try:
                #Generals
                self.config['descripcionrep'] = unicode(xml.find("general/descripcion").text)
                self.config['descripcionproy'] = unicode(xml.find("general/proyecto").text)
                
                #Response time
                self.config['respTime_percentile'] =int(xml.find("responsetime/percentile").text) 
                self.config['respTime_satisfactorio'] =int(xml.find("responsetime/satisfactorio").text) 
                self.config['respTime_tolerante'] = int(xml.find("responsetime/tolerante").text)
                self.config['respTime_scale'] = xml.find("responsetime/scale").text
                
                #Latency time
                self.config['latency_percentile'] =int(xml.find("latencytime/percentile").text) 
                self.config['latency_satisfactorio'] =int(xml.find("latencytime/satisfactorio").text) 
                self.config['latency_tolerante'] = int(xml.find("latencytime/tolerante").text)
                self.config['latency_scale'] = xml.find("latencytime/scale").text

                #Alerts
                self.config['alertas_elapsedporc'] = float(xml.find("alertas/elapsedporc").text)
                self.config['alertas_latencyporc'] = float(xml.find("alertas/latencyporc").text)
                
                #APDEX
#                self.config['apdex_satisfactorio'] =int(xml.find("apdex/satisfactorio").text) 
#                self.config['apdex_tolerante'] = int(xml.find("apdex/tolerante").text)
                
                #Throughput
                self.config['throughput_satisfactorio'] =int(xml.find("throughput/satisfactorio").text) 
                self.config['throughput_tolerante'] = int(xml.find("throughput/tolerante").text)
                self.config['throughput_percentile'] = int(xml.find("throughput/percentile").text)
            except:
                print "It appears that some tags wheren't found in the configuration file, please check the file is correct or delete it to use the default configuration."
                os._exit(15)
            else:
                print "Configuration data loaded successfully"          
        
        # We read the input csv and pass it to an array
        self.requestsArray = []
        self.controlsArray = []
        
        for row in csv.DictReader(open(csvinput,"rb")):
            # Some int transformations for numeric fields
            if row['label'] <> "Debug Sampler":
                row['label'] = unicode(row['label'])
                row["elapsed"] = int(row["elapsed"])
                row["Latency"] = int(row["Latency"])
                try: 
                    row["responseCode"]=int(row['responseCode'])
                except: 
                    row["responseCode"]=int(10000)
                if not row['responseMessage'].startswith("Number of samples in transaction"):
                    self.requestsArray.append(row)
                else:
                    if row['label'].find("(") == -1:
                        try:
                            self.config[row['label']]
                        except KeyError:
                                self.config[row['label']] = []
                                self.config[row['label']].append(int(raw_input("Please insert the Satisfactory time for " + row['label'] + ": ")))
                                self.config[row['label']].append(int(raw_input("Please insert the Tolerable time for " + row['label'] + ": ")))
                    else:
                        satisf = int(row['label'][row['label'].find("(")+1:row['label'].find(",")])
                        tolerante = int(row['label'][row['label'].find(",")+1:row['label'].find(")")])
                        row['label'] = row['label'][:row['label'].find("(")]
                        self.config.setdefault(row['label'],[satisf,tolerante])
                        
                    
                    
                    self.controlsArray.append(row)
            
        # We create the base html file
        self.html = ET.Element('html',{"lang":"en", "xml:lang":"en", "xmlns":r"http://www.w3.org/1999/xhtml"})
        head = ET.SubElement(self.html,'head')
        ET.SubElement(head,'meta',{'http-equiv':'Content-Type', 'content':'text/html;charset=utf-8'})
        ET.SubElement(head,'title').text = "Reporte de Performance"
        css = ET.SubElement(head,'style',{'type':'text/css'})
        css.text = u"""body {font: normal 8pt/16pt Verdana;color: #000000;margin: 10px;}
                    p {font: 8pt/16pt Verdana;margin-top: 0px;}
                    a {font: 8pt Verdana;margin-bottom: 0px;color: #000000;}
                    blockquote a {font: 8pt Verdana;margin-bottom: 0px;color: #3E83C9;}
                    h1 {font: 20pt Verdana;margin:30px 0px 30px 0px;color: #000000;}
                    h2 {font: 15pt Verdana;margin:10px 0px 20px 0px;color: #000000;}
                    h3 {font: 13pt Verdana;margin:5px 0px 10px 0px;color: #000000;}
                    table {border-collapse:collapse;margin-top: 20px;}
                    td {font: normal 8pt Verdana;padding:3px;border-bottom: 1px solid gray;}
                    th {font: bold 10pt Verdana;color:#FFFFFF;font-weight:bold;line-height:1.2;padding:2px 11px;text-align:left;border-right:1px solid #FFFFFF;background-color:#3E83C9;}
                    tr.alt td{background-color:#ECF6FC;}
                    td.red{background-color:#FF0000 !important;}
                    td.yellow{background-color:#FFFF99 !important;}
                    td.blue {background-color:#0066FF !important;}
                    td.gray {background-color:#CCCCCC !important;}
                    td.green {background-color:#33CC33 !important;}
                    blockquote {font: normal 8pt Verdana;}
                    div.section{padding-left:30px;margin-top:100px;border-top: 2px solid gray;}
                    div.subsection{margin-top:50px;}
                    td.time{width:100px;}
                    td.status{width:400px;}
                    table.apdex{margin-left: 80px;}
                    a.back2top{font: bold 10pt Verdana;border-bottom: 3px solid #3E83C9;line-height:50px;padding:0px 280px 5px 20px;text-decoration:none; text-align:right;}"""
        ET.SubElement(head,'script',{'type':'text/javascript', 'src':r'http://ajax.googleapis.com/ajax/libs/jquery/1.2.6/jquery.min.js'}).text = " "
        ET.SubElement(head,'script',{'type':'text/javascript'}).text = r"""$(document).ready(function(){$("tr:even").addClass("alt");});"""
        body = ET.SubElement(self.html,'body')
        ET.SubElement(body,'h1').text = u"Reporte de Performance"
        desc = ET.SubElement(body,'blockquote')
        descrep = ET.SubElement(desc,'b')
        descrep.text = u"Descripción: "
        descrep.tail = self.config['descripcionrep']
        ET.SubElement(desc,'br')
        proyy= ET.SubElement(desc,'b')
        proyy.text = u"Proyecto: " 
        proyy.tail = self.config['descripcionproy']
        ET.SubElement(desc,'br')
        fecha= ET.SubElement(desc,'b')
        fecha.text = u"Fecha: " 
        fecha.tail = time.strftime("%d/%m/%y %H:%M:%S")
        
        indice = ET.SubElement(body,'div',{"id":'indice'})
        indicetit = ET.SubElement(indice,'h2')
        indicetit.text = u"Indice"
        indicelist = ET.SubElement(indice,'ol')
        
        # We set some arrays that will simplify the processing in future calculations
        self.elapsed = [int(row['elapsed']) for row in self.requestsArray]
        self.latency = [int(row['Latency']) for row in self.requestsArray]
        self.duracion = (time.mktime(time.strptime(self.requestsArray[-1]['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(self.requestsArray[-1]['timeStamp'][-5:])) - (time.mktime(time.strptime(self.requestsArray[0]['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(self.requestsArray[0]['timeStamp'][-5:]))
        self.requests = uniq([row['label'] for row in self.requestsArray])
        self.controls = uniq([row['label'] for row in self.controlsArray])
        self.concurrents=[int(row['allThreads']) for row in self.requestsArray]
       
        #We create the directory where the report will be stored
        self.filedir = "Report_%s" % time.strftime("%y-%m-%d_%H-%M-%S")
        os.mkdir(self.filedir)
        self.imagedir = os.path.join(self.filedir,"images")
        os.mkdir(self.imagedir) 

    def addSection(self,title,description, reference=None):
        
        """This function adds a section in the html report.
        
        It recieves the title, description and reference and makes all the 
        standard html structure"""
        
        # We create an id that will later be used by the link in the index
        titleid = unicode(title).replace(" ","").replace("(","").replace(")","").lower()
        body = self.html.find('body')
        indicelist = body.find('div/ol')
        item = ET.SubElement(indicelist,'li')
        ET.SubElement(item,'a',{"href":'#'+titleid}).text = unicode(title)
        seccion = ET.SubElement(body,'div',{"class":"section"})
        ET.SubElement(seccion, 'h2', {"id":titleid}).text = unicode(title) + ": "
        sectdesc = ET.SubElement(seccion, 'blockquote')
        bold = ET.SubElement(sectdesc, 'b')
        bold.text = u"Descripción: "
        bold.tail = description
        if reference is not None:
            ET.SubElement(sectdesc, 'br')
            ET.SubElement(sectdesc, 'br')
            ET.SubElement(sectdesc, 'b').text = u"Referencias: "
            ET.SubElement(sectdesc, 'a', href=reference).text = reference
        # And return the empty section for it to be filled 
        return seccion
        
    def addSubSection(self,title,section):
        
        """This function adds a subsection in the html report.
        
        It recieves the title, and the section in the where it should be 
        placed and makes all the standard html structure"""
        
        # We create the sublist inside the index
        titleid = unicode(title).replace(" ","").replace("(","").replace(")","").lower()
        last_li = self.html.findall(".//div/ol/li")[-1]
        sublist = last_li.find("./ol")
        if sublist is None:
            sublist = ET.SubElement(last_li, "ol")
        sublistli = ET.SubElement(sublist, "li")
        ET.SubElement(sublistli, "a", {"href":"#%s" % titleid}).text = unicode(title)
        
        #Then we create the DIV subsection and return it for filling it up
        return ET.SubElement(section,"div",{"id":titleid, "class":"subsection"})
        
    def processConfiguration(self):
        
        """This adds a simple section that presents all the configuration
        values used for the calculations."""
        
        # Adding a new section and subsection
        seccion = self.addSection("Configuracion",u"A continuacion se detalla la configuracion de los requerimientos ")
        subsection = self.addSubSection(u"Tabla de Configuracion", seccion)
        tabla = ET.SubElement(subsection, 'table', {"class":"Configuracion"})
        thead = ET.SubElement(tabla, 'tr')
        ET.SubElement(thead, 'th').text = u"Variable"
        ET.SubElement(thead, 'th').text = u"Valor"    
        for i in [variable for variable in self.config.items() if variable[0] not in ["descripcionrep", "descripcionproy"]]:        
                    fila = ET.SubElement(tabla, 'tr')
                    ET.SubElement(fila, 'td', {"class":"variable"}).text = unicode(i[0])
                    ET.SubElement(fila, 'td', {"class":"valor"}).text = str(i[1])
            
            
    def processAlerts(self):
        
        """This method finds different problems and displays them in a
        coloured chronological table"""
         
        # We set the standard messages that will be displayed in the report
        red_elapsed = u"El Tiempo de Respuesta supera la media por encima de un " +str (self.config['alertas_elapsedporc']) +"%" 
        yellow_elapsed = u"El Tiempo de Respuesta supera la media por un " +str (self.config['alertas_elapsedporc']) +"%"
        red_latency = u"El latency supera la media por encima de un " + str (self.config['alertas_latencyporc']) + "%"
        yellow_latency = u"El latency supera la media por un " + str (self.config['alertas_latencyporc'])+ "%"
        # We explore the file

        seccion = self.addSection("Alertas",u"A continuacion se detallan los diferentes puntos en el tiempo en que las request al servidor realizados por la aplicación superan la media de esa pagina en toda la ejecución. \n Se valida comparando la media de ese request con cada request con esa URL y se marca en rojo si supera el porcentaje establecido y en amarillo si la diferencia esta dentro del porcentaje establecido. \n Podemos ver la media, el min y max de ese request expresados en Milisegundos acompañando el valor del request. \nTambien podemos observar los Usuarios que estaban activos al momento en que ocurrio el alerta.", "http://technet.microsoft.com/en-us/library/cc757672.aspx")
        subsection1 = self.addSubSection(u"Tabla de Alertas por request", seccion)
        ET.SubElement(subsection1, 'h3').text = u"Tabla de Alertas por request"
        subsection2 = self.addSubSection(u"Tabla de Alertas por control", seccion)
        ET.SubElement(subsection2, 'h3').text = u"Tabla de Alertas por control"
        

        for array in ((self.requestsArray,subsection1,self.requests),(self.controlsArray,subsection2,self.controls)):

            # We caculate all the meassures to compare
            elapsedMin = {}
            elapsedMax = {}
            elapsedAvg = {}
            latencyMin = {}
            latencyMax = {}
            latencyAvg = {}
            for label in array[2]:
                elapsedMin[label] = min([int(row['elapsed']) for row in array[0] if row['label']==label])
                elapsedMax[label] = max([int(row['elapsed']) for row in array[0] if row['label']==label])
                elapsedAvg[label] = avg([int(row['elapsed']) for row in array[0] if row['label']==label])
                latencyMin[label] = min([int(row['elapsed']) for row in array[0] if row['label']==label])
                latencyMax[label] = max([int(row['elapsed']) for row in array[0] if row['label']==label])
                latencyAvg[label] = avg([int(row['elapsed']) for row in array[0] if row['label']==label]) 
            
            # We create the empty list to be filled with alerts
            alertas=[]
            
            for fila in array[0]:
                if fila['URL'] == "null":
                    label = fila['label']
                    filausada = 'label'
                else:
                    label = fila['URL']
                    filausada = 'URL'
                # Elapsed time validations
                if fila['elapsed'] > elapsedAvg[fila['label']] and fila['elapsed'] < (elapsedAvg[fila['label']] + (elapsedAvg[fila['label']] * self.config['alertas_elapsedporc'])):
                    alertas.append({"time":fila['timeStamp'],"color":"yellow","status":yellow_elapsed,"label":unicode(fila[filausada]),"value":fila['elapsed'],"minim":elapsedMin[fila['label']], "averageV":elapsedAvg[fila['label']], "maxim": elapsedMax[fila['label']], "users":fila['allThreads'], "usersId":fila['threadName']})
                elif fila['elapsed'] > elapsedAvg[fila['label']] + (elapsedAvg[fila['label']] * self.config['alertas_elapsedporc']):
                    alertas.append({"time":fila['timeStamp'],"color":"red","status":red_elapsed,"label":unicode(fila[filausada]),"value":fila['elapsed'],"minim":elapsedMin[fila['label']], "averageV":elapsedAvg[fila['label']], "maxim": elapsedMax[fila['label']],"users":fila['allThreads'], "usersId":fila['threadName']})
                # Latency time validations
                if fila['Latency'] > latencyAvg[fila['label']] and fila['Latency'] < (latencyAvg[fila['label']] +(latencyAvg[fila['label']] * self.config['alertas_latencyporc'])):
                    alertas.append({"time":fila['timeStamp'],"color":"yellow","status":yellow_latency,"label":unicode(fila[filausada]),"value":fila['Latency'],"minim":latencyMin[fila['label']], "averageV":latencyAvg[fila['label']], "maxim": latencyMax[fila['label']],"users":fila['allThreads'], "usersId":fila['threadName']})
                elif fila['Latency'] > (latencyAvg[fila['label']] + (latencyAvg[fila['label']] * self.config['alertas_latencyporc'])):
                    alertas.append({"time":fila['timeStamp'],"color":"red","status":red_latency,"label":unicode(fila[filausada]),"value":fila['Latency'],"minim":latencyMin[fila['label']], "averageV":latencyAvg[fila['label']], "maxim": latencyMax[fila['label']],"users":fila['allThreads'], "usersId":fila['threadName']})
            
            # Once we've got the subsection created, we put a table inside it
            tabla = ET.SubElement(array[1], 'table', {"class":"alerts"})
            thead = ET.SubElement(tabla, 'tr')
            ET.SubElement(thead, 'th').text = u"Timestamp"
            ET.SubElement(thead, 'th').text = u"Detalle"
            ET.SubElement(thead, 'th').text = u"Label"
            ET.SubElement(thead, 'th').text = u"Valor"
            ET.SubElement(thead, 'th').text = u"Min"
            ET.SubElement(thead, 'th').text = u"Prom"
            ET.SubElement(thead, 'th').text = u"Max"
            ET.SubElement(thead, 'th').text = u"VUs Act"
            ET.SubElement(thead, 'th').text = u"VUs Id"
            for alerta in alertas:
                fila = ET.SubElement(tabla, 'tr')
                time = ET.SubElement(fila, 'td')
                time.text = unicode(alerta['time'])
                time.set("class","time")
                status = ET.SubElement(fila, 'td')
                status.text = unicode(alerta['status'])
                status.set('class',"status "+alerta['color'])
                label = ET.SubElement(fila, 'td')
                label.text = unicode(alerta['label'])
                detail = ET.SubElement(fila, 'td')
                detail.text = unicode(alerta['value'])
                minim = ET.SubElement(fila, 'td')
                minim.text = unicode(alerta['minim'])
                averageV = ET.SubElement(fila, 'td')
                averageV.text = unicode(alerta['averageV'])
                maxim = ET.SubElement(fila, 'td')
                maxim.text = unicode(alerta['maxim'])
                users = ET.SubElement(fila, 'td')
                users.text = unicode(alerta['users'])
                usersId = ET.SubElement(fila, 'td')
                usersId.text = unicode(alerta['usersId'])



    def processReponseTime(self):
        
        """This method makes different calculations related to the responce
        time of the application.
        
        It creates some tables and graphics and includes them in the report"""

        seccion = self.addSection("Tiempos de Respuesta (Response Time)",u"A continuacion se detallan los Tiempos de Respuesta de la aplicacion en milisegundos.\n Se puede observar una primera tabla donde vemos los tiempos generales de la aplicación (Promedio, minimo y max). Luego se observan los tiempos de respuesta por cada uno de los LABELS (request) realizados por Jmeter al servidor de la aplicacion. Podemos observar la etiqueta el request, junto con los tiempos promedio, min, max, el desvio de la muestra y el percentile solicitado. Ademas de la marca que nos indica que el minimo tiempo obtenido del conjunto de request cuyo etiqueta es la indicada en la columna ""Request"" es mayor al que consideramos tolerante (ROJO), mayor al satisfactorio, pero menor al tolerante (Amarillo) o menor al satisfactorio (Verde). Ejemplo de Tiempo de Respuesta: el tiempo total requerido desde el momento en que  el request es disparado por JMETER hasta que se recibe la respuesta del servidor " , "http://javidjamae.com/2005/04/07/response-time-vs-latency/")
        # General Responce time section
        # This is the general response time table
        subsection = self.addSubSection(u"Tabla de tiempos de respuesta generales", seccion)
        elapsedMin = min(self.elapsed)        
        elapsedMax = max(self.elapsed)
        elapsedAverage = avg(self.elapsed)
        concurrentUsersMax= max(self.concurrents)
        tabla = ET.SubElement(subsection, 'table', {"class":"responsetimegral"})
        thead = ET.SubElement(tabla, 'tr', {"class":"responsetimegral"})
        ET.SubElement(thead, 'th').text = u"Promedio General"
        ET.SubElement(thead, 'th').text = u"Minimo General"
        ET.SubElement(thead, 'th').text = u"Maximo Gral"
        ET.SubElement(thead, 'th').text = u"Max Usuarios Concurrentes"
        fila = ET.SubElement(tabla, 'tr', {"class":"tabla"})
        promgral = ET.SubElement(fila, 'td',)
        promgral.text = str(elapsedAverage) + " ms"
        mingral = ET.SubElement(fila, 'td',)
        mingral.text = str(elapsedMin) + " ms"
        maxgral = ET.SubElement(fila, 'td',)
        maxgral.text = str(elapsedMax) + " ms"
        concUsers = ET.SubElement(fila, 'td',)
        concUsers.text= str(concurrentUsersMax)


        # General Response time graph
        timezero = time.mktime(time.strptime(self.requestsArray[0]['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(self.requestsArray[0]['timeStamp'][-5:])
        timearrayRequests = [(time.mktime(time.strptime(dato['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(dato['timeStamp'][-5:])-timezero, dato['label'], dato['elapsed'], dato['Latency']) for dato in self.requestsArray]
        subsection = self.addSubSection(u"Gráfica de tiempo general", seccion)
        fig = pyplot.figure()
        ax = fig.add_subplot(111)
        l1 = ax.plot([timear[0] for timear in timearrayRequests], [timear[2] for timear in timearrayRequests],'ro', label='Elapsed')
        l2 = ax.plot([timear[0] for timear in timearrayRequests], [timear[3] for timear in timearrayRequests],'yx', label='Latency')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Response vs Latency time (ms)')
        ax.legend(loc=0, shadow=True,  numpoints=1)
        ax.autoscale_view()
#        fig.legend((l1, l2), ('Elapsed', 'Line 2'), 'upper left')
        ax.set_title("General response Time")
        ax.grid(True)
        fig.savefig(os.path.join(self.imagedir,"general_elapsed.png"))
        # We add the subsection and insert the image inside it
        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "general_elapsed.png"),"alt":u"Gráfica de tiempo general"})

        
        
        
        
         # All controls response time with timeStamp
        from matplotlib.dates import epoch2num, num2epoch
        from matplotlib.dates import HourLocator, SecondLocator , MinuteLocator, DateFormatter
        xDateFmt = DateFormatter('%H:%M:%S')      
        timearrayControlsTS = [(epoch2num(time.mktime(time.strptime(dato['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))), dato['label'], dato['elapsed']) for dato in self.controlsArray]
        minTime= min ([dato[0] for dato in timearrayControlsTS])
        maxTime= max([dato[0] for dato in timearrayControlsTS])
        dif= maxTime - minTime 
        subsection = self.addSubSection(u"Gráfica  controles por timeStamp", seccion)
        if self.config['respTime_scale']:
            if self.config['respTime_scale'].lower() == "s":
                fig = pyplot.figure(figsize = (14,7))
            elif self.config['respTime_scale'].lower() == "m":
                fig = pyplot.figure(figsize = (10,5))
        else:    
            fig = pyplot.figure()

        ax = fig.add_subplot(111)
        c= ['r+','b,','y.', 'g1', 'c2', 'm3', 'k4', 'r<', 'b>', 'yD', 'gH', 'c^', 'm_', 'kd','rh', 'bo', 'yp', 'gs', 'cv', 'mx', 'k|']
        p=0             
        for i in self.controls:
            ax.plot_date([str(timear[0]) for timear in timearrayControlsTS if timear[1] == i], [timear[2] for timear in timearrayControlsTS if timear[1] == i], c[p], label=i)
            p+=1
        ax.xaxis.set_major_formatter(xDateFmt)
        if self.config['respTime_scale']:
            if self.config['respTime_scale'].lower() == "s":
                seconds = SecondLocator()
                ax.xaxis.set_major_locator(seconds)
            elif self.config['respTime_scale'].lower() == "m":
                minutes = MinuteLocator()
                ax.xaxis.set_major_locator(minutes)
        else:    
            hours= HourLocator()
            ax.xaxis.set_major_locator(hours)
           
        ax.autoscale_view()
        ax.set_xlabel('TimeStamps')
        ax.set_ylabel('Response time (ms)')
        ax.legend(self.controls, loc=0 , shadow=True, handletextsep=None , numpoints=1, prop=matplotlib.font_manager.FontProperties(size='xx-small' ))
        ax.set_title("Controls Elapsed Time")
        ax.grid(True)
        fig.autofmt_xdate()
        fig.savefig(os.path.join(self.imagedir,"controlsTS_elapsed.png"))
        # We add the subsection and insert the image inside it
        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "controlsTS_elapsed.png"),"alt":u"Gráfica de tiempo por label"})

        
     


##      
        
        
        # Now we start with some calculation for each request
        subsection1 = self.addSubSection(u"Tabla de tiempos de respuesta por request", seccion)
        ET.SubElement(subsection1, 'h3').text = u"Tabla de tiempos de respuesta por request"
        subsection2 = self.addSubSection(u"Tabla de tiempos de respuesta por control", seccion)
        ET.SubElement(subsection2, 'h3').text = u"Tabla de tiempos de respuesta por control"
        respTime = {}
        for array in ((self.requestsArray,subsection1,self.requests,"Requests"),(self.controlsArray,subsection2,self.controls,"Controls")):
            respTime[array[3]]=[]
            # I compare all the a
            for i in array[2]:
                minLabel = min([row['elapsed'] for row in array[0] if row['label']==i])
                maxLabel = max([row['elapsed'] for row in array[0] if row['label']==i])
                avgLabel = avg([row['elapsed'] for row in array[0] if row['label']==i])
                maxUsers = max ([row['allThreads'] for row in array[0] if row['label']==i])
                percLabel = percentile([row['elapsed'] for row in array[0] if row['label']==i], self.config['respTime_percentile'])
                stdevLabel = stdev([row['elapsed'] for row in array[0] if row['label']==i])
                if minLabel < self.config['respTime_satisfactorio']:
                    respTime[array[3]].append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo":maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "green", "maxUsers": maxUsers })
                elif minLabel > self.config['respTime_satisfactorio'] and minLabel < self.config['respTime_tolerante']:
                    respTime[array[3]].append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo": maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "yellow", "maxUsers": maxUsers })
                else:
                    respTime[array[3]].append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo": maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "red", "maxUsers": maxUsers})
    
            
            # This is the "time per request" table
            tabla = ET.SubElement(array[1], 'table', {"class":"responsetime"})
            thead = ET.SubElement(tabla, 'tr')
            ET.SubElement(thead, 'th').text = array[3]
            ET.SubElement(thead, 'th').text = u"min"
            ET.SubElement(thead, 'th').text = u"Promedio"
            ET.SubElement(thead, 'th').text = u"max"
            ET.SubElement(thead, 'th').text = u"Desvío Standard"
            ET.SubElement(thead, 'th').text = str(self.config['respTime_percentile']) + u" %"
            for row in respTime[array[3]]:
                fila = ET.SubElement(tabla, 'tr', {"class":"nombre "})
                nombre = ET.SubElement(fila, 'td',)
                nombre.text = unicode(row['label'])
                minimo = ET.SubElement(fila, 'td', {"class":"minimo"})
                minimo.text = unicode(row['minimo'])
                prom = ET.SubElement(fila, 'td', {"class":"prom"})
                prom.text = unicode(row['prom'])
                maximo = ET.SubElement(fila, 'td', {"class":"maximo"})
                maximo.text = unicode(row['maximo'])
                desviostandard = ET.SubElement(fila, 'td', {"class":"desviostandard"})
                desviostandard.text = unicode(row['desviostandard'])
                percentileValue = ET.SubElement(fila, 'td', {"class":"percentileValue"})
                percentileValue.text = unicode(row['percentileValue'])
                color = ET.SubElement(fila, 'td', {"class":row['color']})

            # Worst Labels response time (PROM)
            # We sort the respTime array by prom
            subsection = self.addSubSection(array[3] + u" con el peor tiempo de respuesta (prom)", array[1])
            from operator import itemgetter
            respTime[array[3]] = sorted(respTime[array[3]], key=itemgetter('prom'))
            # And display only the 30% worst labels
            worstLabels = respTime[array[3]][-(int(math.ceil(0.3*len(respTime[array[3]])))):]
            # Now we make the graph with that labels
            fig = pyplot.figure()
            ax = fig.add_subplot(111)
            xlocations = na.array(range(len(worstLabels)))+0.5
            width = 0.5
            ax.autoscale_view()
            from matplotlib.transforms import offset_copy
            transOffset = offset_copy(ax.transData, fig=fig, y=0.10, units='inches')
            ax.bar(xlocations, [dato['prom'] for dato in worstLabels], width=width)
#            a=range(len(worstLabels)) 
            for x, y in zip(na.array(range(len(worstLabels)))+0.5, [dato['prom'] for dato in worstLabels]):                
                ax.text(x, y, '%d' % (int(y)), transform=transOffset)
            ax.set_xticks(xlocations+ width/2)
            ax.set_xticklabels([dato['label'] for dato in worstLabels], rotation=-15, horizontalalignment="left", size="xx-small")
            ax.set_xlim(0, xlocations[-1]+width*2)
            ax.set_title(array[3] + " with worst Response Time (prom)")
            fig.savefig(os.path.join(self.imagedir,array[3].lower() + "resptime_prom.png"))
            ET.SubElement(subsection, 'img', {"src":os.path.join("images", array[3].lower() + "resptime_prom.png"),"alt":u"Gráfica de Tiempo por " + array[3]})
            
            
            
            # Worst Labels response time (MAX)
            # We sort the respTime array by prom
            subsection = self.addSubSection(array[3] + u" con el peor tiempo de respuesta (max)", array[1])
            from operator import itemgetter
            respTime[array[3]] = sorted(respTime[array[3]], key=itemgetter('maximo'))
            # And display only the 30% worst labels
            worstLabels = respTime[array[3]]
            # Now we make the graph with that labels
            fig = pyplot.figure(figsize=(int(len(worstLabels)*0.85), 5))
            ax = fig.add_subplot(111)
            xlocations = na.array(range(len(worstLabels)))+0.5
            width = 0.5
            ax.autoscale_view()
            ax.bar(xlocations, [dato['maximo'] for dato in worstLabels], width=width)
            ax.set_xticks(xlocations+ width/2)
            ax.set_xticklabels([dato['label'] for dato in worstLabels], rotation=-15, horizontalalignment="left", size="xx-small")
            ax.set_xlim(0, xlocations[-1]+width*2)
            ax.set_title(array[3] + " with worst Response Time (max)")
            fig.savefig(os.path.join(self.imagedir,array[3].lower() + "resptime_max.png"))
            ET.SubElement(subsection, 'img', {"src":os.path.join("images", array[3].lower() + "resptime_max.png"),"alt":u"Gráfica de Tiempo por " + array[3]})

        # All Requets response time  vs Virtual Users
        worstLabels = respTime['Requests'][-(int(math.ceil(0.3*len(respTime['Requests'])))):]
        timezero = time.mktime(time.strptime(self.requestsArray[0]['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(self.requestsArray[0]['timeStamp'][-5:])
        timearrayRequests = [(time.mktime(time.strptime(dato['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(dato['timeStamp'][-5:])-timezero, dato['label'], dato['elapsed'], dato['allThreads'] ) for dato in self.requestsArray if  dato['label'] in [row['label'] for row in worstLabels]]
        subsection = self.addSubSection(u"Gráfica peores Requests Reponse Time vs Concurrent Users ", seccion)
        fig = pyplot.figure(figsize = (10,5))
        ax = fig.add_subplot(111)      
        c= ['ro','go', 'co', 'mo', 'yo', 'cd', 'm3', 'k4', 'r<', 'y>', 'yD', 'gH', 'c^', 'm_', 'kd','rh', 'yo', 'yp', 'gs', 'cv', 'mx', 'k|']
        p=0             
        for i in worstLabels:
            ax.plot([timear[0] for timear in timearrayRequests if timear[1] == i['label']], [timear[2] for timear in timearrayRequests if timear[1] == i['label']], c[p], label=i['label'])            
            p+=1
        ax1= pyplot.twinx()
        ax1.plot([timear[0] for timear in timearrayRequests],[timear[3] for timear in timearrayRequests] , 'b-', label='Users')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Response Time (ms)')
        ax1.set_ylabel("Concurrent Users", color='b')
        ax.autoscale_view()
        ax.set_title("Requests with poor Response Time vs Concurrent Users")
        ax.grid(True)
        ax.legend( uniq([row[1][:15]+"..." for row in timearrayRequests]), loc=0 , shadow=True, handletextsep=None , numpoints=1, prop=matplotlib.font_manager.FontProperties(size='xx-small' ))
        fig.savefig(os.path.join(self.imagedir,"Requests_Users.png"))
        # We add the subsection and insert the image inside it
        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "Requests_Users.png"),"alt":u"Gráfica de tiempo vs usuarios"})


        # All Requets response time  vs Virtual Users 2
        worstLabels = respTime['Requests'][-(int(math.ceil(0.3*len(respTime['Requests'])))):]
#        print worstLabels
#        tiempos = {} 
#        for i in range(1,concurrentUsersMax):
#            tiempos[i].setdefault(i,0)
#            for row2 in [row for row in self.requestsArray if row['label'] in worstLabels or int(row['allThreads']) == i]:
#                if tiempos[i][row2['label']] < row2['elapsed']:
#                    tiempos[i][row2['label']] = (row2['label'],row2['elapsed'])
#        print tiempos
        
        timezero = time.mktime(time.strptime(self.requestsArray[0]['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(self.requestsArray[0]['timeStamp'][-5:])
        timearrayRequests = [(time.mktime(time.strptime(dato['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S"))+ float(dato['timeStamp'][-5:])-timezero, dato['label'], dato['elapsed'], int(dato['allThreads']) ) for dato in self.requestsArray if  dato['label'] in [row['label'] for row in worstLabels] ]
        from operator import itemgetter      

#        respTime[array[3]] = sorted(respTime[array[3]], key=itemgetter('maximo'))

        timearrayRequests= sorted(timearrayRequests, key=itemgetter(0))
        subsection = self.addSubSection(u"Gráfica Requests Reponse Time vs Concurrent Users ", seccion)
        fig = pyplot.figure(figsize = (10,5))
        ax = fig.add_subplot(111)      
        c= ['ro-','go', 'co', 'mo', 'yo', 'co', 'mo', 'k4', 'r<', 'y>', 'yD', 'gH', 'c^', 'm_', 'kd','rh', 'yo', 'yp', 'gs', 'cv', 'mx', 'k|']
        p=0  
                          
#        for i in worstLabels[:1]:
##            for t in range(1,concurrentUsersMax): 
#            for row in [fila for fila in timearrayRequests if fila[1]==i['label']]: 
#                print "++++++++++++"
#                print row
#                print "---------"
#                print row[1] 
#                print "*********"
#                print [timear[3] for timear in timearrayRequests if timear[1] == i['label'] and int(timear[3])==t]             
#    #                ax.plot([timear[3] for timear in timearrayRequests if timear[1] == i['label'] and int(timear[3])==t], [timear[2] for timear in timearrayRequests if timear[1] == i['label'] and timear[2] == i['maximo'] and int(timear[3])==t], c[p], label=i['label'])            
#            p+=1

#        timearrayRequests= sorted(timearrayRequests, key=itemgetter(0))
#        subsection = self.addSubSection(u"Gráfica Requests Reponse Time vs Concurrent Users ", seccion)
#        fig = pyplot.figure(figsize = (10,5))
#        ax = fig.add_subplot(111)      
#        c= ['ro-','go', 'co', 'mo', 'yo', 'co', 'mo', 'k4', 'r<', 'y>', 'yD', 'gH', 'c^', 'm_', 'kd','rh', 'yo', 'yp', 'gs', 'cv', 'mx', 'k|']
#        p=0  
#                          
#        for i in worstLabels[:1]:
#            print i['label']
#            ax.plot([timear[3] for timear in timearrayRequests if timear[1] == i['label']], [timear[2] for timear in timearrayRequests if timear[1] == i['label']], c[p], label=i['label'])            
#            p+=1

#        ax1= pyplot.twinx()
#        ax1.plot([timear[0] for timear in timearrayRequests],[timear[3] for timear in timearrayRequests] , 'b-', label='Users')
#        ax.set_xlabel('Time (s)')
#        ax.set_ylabel('Response Time (ms)')
#        ax1.set_ylabel("Concurrent Users", color='b')
#        ax.autoscale_view()
#        ax.set_title("Requests Response Time vs Concurrent Users")
#        ax.grid(True)
##        ax.legend( uniq([row[1][:15]+"..." for row in timearrayRequests]), loc=0 , shadow=True, handletextsep=None , numpoints=1, prop=matplotlib.font_manager.FontProperties(size='xx-small' ))
#        fig.savefig(os.path.join(self.imagedir,"Requests_Users2.png"))
#        # We add the subsection and insert the image inside it
#        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "Requests_Users2.png"),"alt":u"Gráfica de tiempo vs usuarios"})





    def processLatencyTime(self):
        
        """This method makes different calculations related to the latency
        time of the application.
        
        It creates some tables and graphics and includes them in the report"""

        seccion = self.addSection("Tiempos de Latency (Latency Time)",u"A continuacion se detallan los Tiempos de Latency de la aplicacion en milisegundos.Tiempo desde el momento en que se dispara la peticion (request) por Jmeter hasta el 1º byte de respuesta es recibido desde la aplicacion.\n  " , "http://www.webperformancematters.com/journal/2007/7/24/latency-bandwidth-and-response-times.html")
        # General Latency time section
        # This is the general latency time table
        subsection = self.addSubSection(u"Tabla de tiempos de latency generales", seccion)
        latencyMin = min(self.latency)        
        latencyMax = max(self.latency)
        latencyAverage = avg(self.latency)
        tabla = ET.SubElement(subsection, 'table', {"class":"latencytimegral"})
        thead = ET.SubElement(tabla, 'tr', {"class":"latencytimegral"})
        ET.SubElement(thead, 'th').text = u"Promedio General"
        ET.SubElement(thead, 'th').text = u"Minimo General"
        ET.SubElement(thead, 'th').text = u"Maximo Gral"
        fila = ET.SubElement(tabla, 'tr', {"class":"tabla"})
        promgral = ET.SubElement(fila, 'td',)
        promgral.text = str(latencyAverage) + " ms"
        mingral = ET.SubElement(fila, 'td',)
        mingral.text = str(latencyMin) + " ms"
        maxgral = ET.SubElement(fila, 'td',)
        maxgral.text = str(latencyMax) + " ms"


        # Now we start with some calculation for each request
        subsection = self.addSubSection(u"Tabla de latency por request", seccion)
        ET.SubElement(subsection, 'h3').text = u"Tabla de latency por request"
        latencyTime=[]
        # I compare all the a
        for i in self.requests:
            minLabel = min([row['Latency'] for row in self.requestsArray if row['label']==i])
            maxLabel = max([row['Latency'] for row in self.requestsArray if row['label']==i])
            avgLabel = avg([row['Latency'] for row in self.requestsArray if row['label']==i])
            percLabel = percentile([row['Latency'] for row in self.requestsArray if row['label']==i], self.config['latency_percentile'])
            stdevLabel = stdev([row['Latency'] for row in self.requestsArray if row['label']==i])
            if minLabel < self.config['latency_satisfactorio']:
                latencyTime.append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo":maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "green"})
            elif minLabel > self.config['latency_satisfactorio'] and minLabel < self.config['latency_tolerante']:
                latencyTime.append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo": maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "yellow"})
            else:
                latencyTime.append({"label":i, "minimo":minLabel,"prom":avgLabel,"maximo": maxLabel , "desviostandard": stdevLabel, "percentileValue": percLabel, "color": "red"})

        
        # This is the "Latency per request" table
        tabla = ET.SubElement(subsection, 'table', {"class":"Latency"})
        thead = ET.SubElement(tabla, 'tr')
        ET.SubElement(thead, 'th').text = "Requests"
        ET.SubElement(thead, 'th').text = u"min"
        ET.SubElement(thead, 'th').text = u"Promedio"
        ET.SubElement(thead, 'th').text = u"max"
        ET.SubElement(thead, 'th').text = u"Desvío Standard"
        ET.SubElement(thead, 'th').text = str(self.config['latency_percentile']) + u" %"
        for row in latencyTime:
            fila = ET.SubElement(tabla, 'tr', {"class":"nombre "})
            nombre = ET.SubElement(fila, 'td',)
            nombre.text = unicode(row['label'])
            minimo = ET.SubElement(fila, 'td', {"class":"minimo"})
            minimo.text = unicode(row['minimo'])
            prom = ET.SubElement(fila, 'td', {"class":"prom"})
            prom.text = unicode(row['prom'])
            maximo = ET.SubElement(fila, 'td', {"class":"maximo"})
            maximo.text = unicode(row['maximo'])
            desviostandard = ET.SubElement(fila, 'td', {"class":"desviostandard"})
            desviostandard.text = unicode(row['desviostandard'])
            percentileValue = ET.SubElement(fila, 'td', {"class":"percentileValue"})
            percentileValue.text = unicode(row['percentileValue'])
            color = ET.SubElement(fila, 'td', {"class":row['color']})

        # Worst Labels Latency time
        # We sort the LatencyTime array by prom
        subsection = self.addSubSection(u"Requests con el peor tiempo de Latency", subsection)
        from operator import itemgetter
        latencyTime = sorted(latencyTime, key=itemgetter('prom'))
        # And display only the 30% worst labels
        worstLabels = latencyTime[-(int(math.ceil(0.3*len(latencyTime)))):]
        # Now we make the graph with that labels
        fig = pyplot.figure()
        ax = fig.add_subplot(111)
        xlocations = na.array(range(len(worstLabels)))+0.5
        width = 0.5
        ax.autoscale_view()
        ax.bar(xlocations, [dato['prom'] for dato in worstLabels], width=width)
        ax.set_xticks(xlocations+ width/2)
        ax.set_xticklabels([dato['label'] for dato in worstLabels], rotation=-15, horizontalalignment="left", size="xx-small")
        ax.set_xlim(0, xlocations[-1]+width*2)
        ax.set_title("Requests with worst Latency Time")
        fig.autofmt_xdate()
        fig.savefig(os.path.join(self.imagedir,"requestslatency.png"))
        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "requestslatency.png"),"alt":u"Gráfica de Tiempo por Request"})

    def processThroughput(self):
        
        """This method calculates the throughput and displays the results in
        a table and graphic"""
        
        throughput= []
        
        for i in self.requests:           
            labelTimes = [(time.mktime(time.strptime(row['timeStamp'][:-5], "%m/%d/%Y %H:%M:%S")) + float(row['timeStamp'][-5:]), row['elapsed']) for row in self.requestsArray if row['label']==i]
            minStartTime = min([row[0] for row in labelTimes])
            maxEndTime = max([(row[0] + row[1]) for row in labelTimes])
            labelTimeTotal = maxEndTime - minStartTime
            cantRequest= len ([row['responseCode'] for row in self.requestsArray if row['label']==i and int(row['responseCode'])<500]) 
#            print i 
#            print "cant request"
#            print cantRequest
#            print "len"
#            print len(labelTimes)
            labelThroughput = (cantRequest / float(labelTimeTotal))*1000
            if labelThroughput < self.config['throughput_satisfactorio']:
                throughput.append({'nombre':unicode(i), 'throughput': "%.10f" % labelThroughput, "color": "green"})
            elif labelThroughput > self.config['throughput_satisfactorio'] and labelThroughput < self.config['throughput_tolerante']:
                throughput.append({'nombre':unicode(i), 'throughput': "%.10f" % labelThroughput, "color": "yellow"})
            else:
                throughput.append({'nombre':unicode(i), 'throughput': "%.10f" % labelThroughput, "color": "red"})    

        seccion = self.addSection("Rendimiento (Throughput)",u"El rendimiento representa el numero real de solicitudes por minuto que el servidor maneja. Este calculo incluye los retrasos (timers) que se han añadido a la prueba y el tiempo de procesamiento interior de JMeter. La ventaja de hacer el calculo de esta forma es que este numero representa algo real. Su servidor de hecho maneja muchas solicitudes por minuto, y puede aumentar el numero de hilos y / o disminuir los retrasos (timers) para descubrir el maximo rendimiento del servidor. Throughput = Number of requests / Total time to issue the requests. A continuacion se detallan los valores de rendimiento para cada uno de los request realizados. " , "http://www.forsythesunsolutions.com/node/114")
        subsection = self.addSubSection(u"Tabla de Throughput", seccion)
        tabla = ET.SubElement(subsection, 'table', {"class":"Rendimiento"})
        thead = ET.SubElement(tabla, 'tr')
        ET.SubElement(thead, 'th').text = u"Request"
        ET.SubElement(thead, 'th').text = u"Valor (Request por segundo)"
        
        for control in throughput:
            fila = ET.SubElement(tabla, 'tr', {"class":"nombre"})
            nombre = ET.SubElement(fila, 'td',)
            nombre.text = unicode(control['nombre'])
            valor = ET.SubElement(fila, 'td', {"class":"valor"})
            valor.text = unicode(control['throughput'])
            color = ET.SubElement(fila, 'td', {"class":control['color']})
   
        # Labels throughput
        from operator import itemgetter
        throughput = sorted(throughput, key=itemgetter('throughput'))
        maxLabels = int(math.ceil(0.3*len(throughput)))
        throughput = throughput[:maxLabels]
        fig = pyplot.figure()
        ax = fig.add_subplot(111)
        xlocations = na.array(range(len(throughput)))+0.5
        width = 0.5
        ax.bar(xlocations, [float(dato['throughput']) for dato in throughput], width=width)
        ax.set_xticks(xlocations+ width/2)
        ax.set_xticklabels([unicode(dato['nombre']) for dato in throughput], rotation=-15, horizontalalignment="left", size="xx-small")
        ax.set_xlim(0, xlocations[-1]+width*2)
        ax.set_title("Labels with poor Throughput")
        ax.autoscale_view()
        fig.savefig(os.path.join(self.imagedir,"throughput.png"))
        subsection = self.addSubSection(u"Labels con el peor Throughput", seccion)
        ET.SubElement(subsection, 'img', {"src":os.path.join("images","throughput.png"), "alt":"Labels con el peor Throughput"})
#   
    def processApdex(self):
        #Criterio Apdex
        apdex=[]
                
        #Seteamos los contadores para cada control en 0
        contarTotalControl = {}.fromkeys(self.controls,0)
        contarSatisfacControl= {}.fromkeys(self.controls,0)
        contarToleranteControl= {}.fromkeys(self.controls,0)
        contarFallidosControl= {}.fromkeys(self.controls,0)
        
        
        for row in self.controlsArray:
            
            contarTotalControl[row['label']] = contarTotalControl[row['label']] + 1
                       
            if row['elapsed'] < self.config[row['label']][0]:
                contarSatisfacControl[row['label']]+= 1
            elif row['elapsed'] < self.config[row['label']][1]:
                contarToleranteControl[row['label']] += 1 
            else:
                contarFallidosControl[row['label']] += 1
        for control in [row for row in self.controls if contarTotalControl[row]]:
            indice= (contarSatisfacControl[control] + (contarToleranteControl[control] / 2.0))/ float(contarTotalControl[control])
            if (float(indice)<= 1 and float(indice) >= 0.95):
                color="blue"
            elif (float(indice)<= 0.94 and float(indice)>= 0.85):
                color="green"
            elif (float(indice)<= 0.84 and float(indice) >= 0.7):
                color="yellow"
            elif (float(indice)<= 0.69 and float(indice) >= 0.5):
                color="red"
            elif (float(indice)<= 0.49):
                color="gray"       
            
            apdex.append({"nombre":control,"color":color,"satisfactorio":self.config[control][0],"tolerante":self.config[control][1],"total":contarTotalControl[control],"satisfactorios":contarSatisfacControl[control],"tolerantes":contarToleranteControl[control], "fallidos":contarFallidosControl[control], "indice": indice})
        
        seccion = self.addSection("Criterio Apdex",u"A continuacion se detallan los valores del criterio APDEX. Este criterio es un estandard que define lineamientos para reportar la performance de una aplicación. Este criterio se basa en la creacion de un indice para la metrica en estudio, convirtiendo esta metrica en un numero uniforme del 0 al 1 (0=Usuarios no satisfechos a 1= Todos los Usuarios satisfechos). Se basa en la escala Excelente (0.95 a 1), Bueno(0.85 a 0.94), Regular(0.7 a 0.84), deficiente (0.5 a 0.69) e inaceptable (0 a 0.49). Se basa en la formula xxxx para determinar el indicador APDEX" , "http://www.apdex.org")
        subsection = self.addSubSection(u"Tabla APDEX", seccion)
        tabla = ET.SubElement(subsection, 'table', {"class":"apdex"})
        encabezado= ET.SubElement(tabla, 'tr', {"class":"encabezado"})
        espacio=ET.SubElement(encabezado, 'th', {"class":"vacio"})
        criterio=ET.SubElement(encabezado, 'th', {"class":"criterio", "colspan":"2"})
        criterio.text=u"Criterio"
        resultado=ET.SubElement(encabezado, 'th', {"class":"resultado", "colspan":"4"})
        resultado.text=u"Resultados"
        thead = ET.SubElement(tabla, 'tr')
        ET.SubElement(thead, 'th').text = u"Transacción"
        ET.SubElement(thead, 'th').text = u"Se considera Satisfactorio"
        ET.SubElement(thead, 'th').text = u"Se considera Tolerante"
        ET.SubElement(thead, 'th').text = u"Total"
        ET.SubElement(thead, 'th').text = u"Cant. Satisfactorios"
        ET.SubElement(thead, 'th').text = u"Cant. Tolerantes"
        ET.SubElement(thead, 'th').text = u"Cant. Fallidos"
        ET.SubElement(thead, 'th').text = u"Indice APDEX"
        for control in apdex:
            fila = ET.SubElement(tabla, 'tr', {"class":"nombre"})
            nombre = ET.SubElement(fila, 'td',)
            nombre.text = unicode(control['nombre'])
            satisfactorio = ET.SubElement(fila, 'td', {"class":"satisfactorio"})
            satisfactorio.text = unicode(control['satisfactorio'])
            tolerante = ET.SubElement(fila, 'td', {"class":"tolerante"})
            tolerante.text = unicode(control['tolerante'])
            total = ET.SubElement(fila, 'td', {"class":"total"})
            total.text = unicode(control['total'])
            satisfactorios = ET.SubElement(fila, 'td', {"class":"satisfactorios"})
            satisfactorios.text = unicode(control['satisfactorios'])
            tolerantes = ET.SubElement(fila, 'td', {"class":"tolerantes"})
            tolerantes.text = unicode(control['tolerantes'])
            fallidos = ET.SubElement(fila, 'td', {"class":"fallidos"})
            fallidos.text = unicode(control['fallidos'])
            indice = ET.SubElement(fila, 'td', {"class":control['color']})
            indice.text = unicode(control['indice'])
        
        #Here we generate the Bar Graph
        fig = pyplot.figure()
        ax = fig.add_subplot(111)
        data = [(control['nombre'],control['indice'],control['color']) for control in apdex]
        xlocations = na.array(range(len(data)))+0.5
        width = 0.5
        ax.autoscale_view()
        ax.bar(xlocations, [dato[1] for dato in data], width=width, color=[dato[2] for dato in data])
        ax.set_yticklabels((0,0.25,0.5,0.75,1))
        ax.set_yticks((0,0.25,0.5,0.75,1,1.25))
        ax.set_xticks(xlocations+ width/2)
        ax.set_xticklabels([dato[0] for dato in data], rotation=-20, horizontalalignment="left", size="xx-small")
        ax.set_xlim(0, xlocations[-1]+width*2)
        ax.set_title("APDEX")
        fig.savefig(os.path.join(self.imagedir,"apdex.png"))
        subsection = self.addSubSection(u"Gráfica de valores APDEX", seccion)
        ET.SubElement(subsection, 'img', {"src":os.path.join("images", "apdex.png"),"alt":u"Gráfica apdex"})

   
    
    def generate(self, htmloutput):
        for div in self.html.findall(".//div"):
            if div.get("class") == "section":
                footer = ET.SubElement(div, "p")
                ET.SubElement(footer, "a", {"class":"back2top","href":"#indice"}).text = "Volver"
        w3c = ET.SubElement(self.html.find("body"), "a", {"href":r"http://validator.w3.org/check?uri=referer"})
        ET.SubElement(w3c, "img", {"src":r"http://www.w3.org/Icons/valid-xhtml10-blue", "alt":"Valid XHTML 1.0 Transitional", "height":"31", "width":"88"})
        tree = ET.ElementTree(self.html)
        ofile = os.path.join(self.filedir,htmloutput)
        print u"writing report: %s" % ofile
        outfile = open(ofile, 'w')
        outfile.write(r"""<?xml version="1.0" encoding="utf-8"?>""")
        outfile.write(r"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">""") 
        tree._write(outfile, tree._root, 'utf-8', {})
        outfile.close()

if __name__ == "__main__":
    start = time.clock()
    report = Report(options.input)
    report.processConfiguration()
    report.processAlerts()
    report.processReponseTime()
    report.processLatencyTime()
    report.processThroughput()
    report.processApdex()
    report.generate(options.output)
    print "Time elapsed: ", time.clock() - start