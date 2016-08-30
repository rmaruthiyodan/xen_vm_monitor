#!/usr/bin/python

# Xen_monitor project
# Author: Ratish Maruthiyodan
# Description: Provides the front end, that plots graphs using the VM resource stats that have been collected in the MySQL DB.
# 25 Dec 2013


import wx
import wx.grid
#import wxspreadsheet

from matplotlib.figure import Figure
import numpy as np
# import the WxAgg FigureCanvas object, that binds Figure to
# WxAgg backend. In this case, this is also a wxPanel
from matplotlib.backends.backend_wxagg import \
FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx
import matplotlib.dates as mdates
import MySQLdb
from datetime import datetime, timedelta

class UI_init(wx.Frame):
	def __init__(self, parent, title):
		"""Constructor"""
		wx.Frame.__init__(self, parent=None, title=title, size=(1350, 800))
		self.InitUI()
		self.Centre()
		self.Show()
		
	def VBD_DataPopulate(self, vmslist=[],sel_phydisk=[]):
		# Open database connection
		k = 0
		i = 0
		#db = MySQLdb.connect("10.176.255.55","xenmon","xenmon123","xen_monitor" )
		db = MySQLdb.connect(self.DB_IP, self.DB_User, self.DB_Password, self.DB_Name)

		# prepare a cursor object using cursor() method
		cursor = db.cursor()
		dlg = wx.MessageDialog(self, 'DB Connected! Please wait while we are fetching data...', 'Patience...', wx.ICON_INFORMATION)
		dlg.ShowModal()
		dlg.Destroy()
		
		sql = "SELECT * FROM vbd_stat where time > '" + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		#+ " and time < '" + "2014-01-14 20:00:00" + "'"
		sql_conditions = ''
		if len(vmslist) > 0:
			sql_conditions = " and ("
			k = 0
			while k < len(vmslist):
				if k > 0:
					sql_conditions = sql_conditions + " or "	
				sql_conditions = sql_conditions + " name = '" + vmslist[k] + "'"
				k = k + 1
			sql_conditions = sql_conditions + ")"		
		
		
		if (len(sel_phydisk) > 0):
			sql_conditions = sql_conditions + " and ("
			k = 0
			while k < len(sel_phydisk):
				if k > 0:
					sql_conditions = sql_conditions + " or "
				sql_conditions = sql_conditions + " backend = '" + sel_phydisk[k] + "'"
				k = k + 1
				
			sql_conditions = sql_conditions + ")"
			
		
		if k > 0:
			sql = sql + sql_conditions
		print 'SQL Query is : ', sql
		
		self.myDataList = []
		
		# Execute the SQL command
		cursor.execute(sql)
		# Fetch all the rows in a list of lists.
		results = cursor.fetchall()
		for row in results:
			time = row[0]
			name = row[1]
			vbd = row[2]
			phy_disk = row[3]
			if row[4] >= 0 and row[4] < 12000000:
				rdmbs = row[4]/1024
			else:
				rdmbs = 0
			
			if row[5] >= 0 and row[5] < 12000000:
				wrmbs = row[5]/1024
			else:
				wrmbs = 0
			#print "Time=%s,name=%s,vcpu=%d,phycpu=%s,pcent_usage=%d" % (time, name, vcpu, phycpu, pcent_usage)
			#if  < 101:
			self.myDataList.append({'Time':time, 'Name':name, 'vbd':vbd,'phy_disk':phy_disk, 'rdmbs':rdmbs, 'wrmbs':wrmbs})
			#print 'Time ',time, 'Name ', name, 'vbd ' , vbd,'phy_disk ', phy_disk, 'rdmbs ',rdmbs, 'wrmbs ',wrmbs
			i = i + 1

		sql = "Select distinct name,vbd FROM vbd_stat where time > '" + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		if k > 0:
			sql = sql + sql_conditions
			print 'Distinct SQL statement', sql
		k=0	
			
		cursor.execute(sql)
		results1 = cursor.fetchall()
		prev_name = ''
		self.all_vbds = [[]]
		j = -1
		for row1 in results1:
			if prev_name != row1[0]:
				prev_name = row1[0]
				self.all_vbds.append([])
				j = j + 1
			self.all_vbds[j].append(0)
			print prev_name , ' :' , self.all_vbds[j]
				
		db.close()
		
		if i == 0:
			dlg = wx.MessageDialog(self, 'No data captured in the DB for the said time period...', 'Ooopps...', wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
			return
		
		print 'row count = ', i
		
		self.grid1.ClearGrid()
		
		current_cols, new_cols = (self.grid1.GetNumberCols(), 7)
		if new_cols < current_cols:
        #- Delete rows:
			self.grid1.DeleteCols(0, current_cols - new_cols, True)

		if new_cols > current_cols:
        #- append rows:
			self.grid1.AppendCols(new_cols - current_cols)
			
		current_rows, new_rows = (self.grid1.GetNumberRows(), i)
		if new_rows < current_rows:
        #- Delete rows:
			self.grid1.DeleteRows(0, current_rows - new_rows , True)

		if new_rows > current_rows:
        #- append rows:
			self.grid1.AppendRows(new_rows - current_rows)		
		
		self.grid1.SetColLabelValue(0, "Time                                 ")
		self.grid1.SetColLabelValue(1, "VM Name       ")
		self.grid1.SetColLabelValue(2, "VBD   ")
		self.grid1.SetColLabelValue(3, "Phy Disk/Image          ")
		self.grid1.SetColLabelValue(4, "Rd MB/s")
		self.grid1.SetColLabelValue(5, "Wr MB/s")
		self.grid1.SetColLabelValue(6, "Total usage MB/s  ")
		
		#print i
		#print 
		j=0
		while j<i:
			self.grid1.SetCellValue(j,0, str(self.myDataList[j]['Time']))
			self.grid1.SetCellValue(j,1, self.myDataList[j]['Name'])
			self.grid1.SetCellValue(j,2, str(self.myDataList[j]['vbd']))
			self.grid1.SetCellValue(j,3, self.myDataList[j]['phy_disk'])
			rx=0
			tx=0
			if self.myDataList[j]['rdmbs'] >= 0 and self.myDataList[j]['rdmbs'] < 12000000:
				rx = self.myDataList[j]['rdmbs'] * 8
				
			self.grid1.SetCellValue(j,4, str(rx))							
							
			if 	self.myDataList[j]['wrmbs'] >= 0 and self.myDataList[j]['wrmbs'] < 12000000:
				tx = self.myDataList[j]['wrmbs'] * 8
				
			self.grid1.SetCellValue(j,5, str(tx))
						
			self.grid1.SetCellValue(j,6,str(rx + tx))
				
			j=j+1
				
		self.grid1.AutoSizeColumn(0,)
		self.grid1.AutoSizeColumn(1,)
		self.grid1.AutoSizeColumn(2,)
		self.grid1.AutoSizeColumn(3,)
		self.grid1.AutoSizeColumn(4,)
		self.grid1.AutoSizeColumn(5,)
		self.grid1.AutoSizeColumn(6,)
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		#x = [ 0 , 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
		#y = [ 10, 2, 5, 6, 4 , 5 , 7, 4, 7, 5, 20, 6, 8, 30 , 9, 7, 8, 9, 2, 7, 5, 8, 9 ,7, 5, 6]
		#self.axes.plot(x, y)
		#self.canvas.draw()
		
		self.PlotGraph_Disk_stat(i)
		
	
	def PlotGraph_Disk_stat(self, num_elements):

		
		xtime = []
		vms = []
		vbd_rd = [[]]
		vbd_wr = [[]]
		num_vbds = []
		#
		# Extracting DB contents into a 2-dimentional array to retrieve each VM wise Avg %cpu usage such as 
		# a[0][1]=40%   --> here [0] represents the first time interval and [1] represents the Guest VM
		# the range would be like a[0 - (number of samples-1)][0 - (num of VMs -1)]
		#
		
		time_count=0
		prev_time = ''
		prev_name = ''
		i=0
		j=0
		match=0
		num_vms = 0		
		while i < num_elements:
			cur_time = str(self.myDataList[i]['Time'])
						
			if  cur_time != prev_time:
				time_count = time_count +1
				prev_time = cur_time
				xtime.append(self.myDataList[i]['Time'])
				#print xtime[time_count-1]
				#j = 0
				vbd_rd.append([])
				vbd_wr.append([])
				no_vbd=0
				k=0
			# protecting against cases where VM stats for a Guest/disk won't be available for specific time stamp
			# due to vm shutdown or disk detachment
			# otherwise, this will cause error while plotting the graph in such cases 
			#(due to difference with the number of X & Y cordinates)
			
				while k < len(self.all_vbds):
					vbd_rd[time_count-1].append([])
					vbd_wr[time_count-1].append([])
					m=0
					while m < len(self.all_vbds[k]):
						vbd_rd[time_count-1][k].append(0)
						vbd_wr[time_count-1][k].append(0)
						m = m + 1
					k = k + 1
						
			
			if self.myDataList[i]['Name'] != prev_name:
				match=0
				j = 0
				no_vbd = 0
				while j < num_vms:
					if self.myDataList[i]['Name'] == vms[j]:
						match = 1
						prev_name = self.myDataList[i]['Name']						
						break
					j = j+1	
				num_vbds.append(0)
				if match == 0:
					j = num_vms
					vms.append(self.myDataList[i]['Name'])
					num_vms = num_vms + 1
					#vbd_rd[time_count-1].append([])
					#vbd_wr[time_count-1].append([])
					prev_name = self.myDataList[i]['Name']
					num_vbds.append(0)
			try:		
				vbd_rd[time_count-1][j][no_vbd]= self.myDataList[i]['rdmbs']
				vbd_wr[time_count-1][j][no_vbd] = self.myDataList[i]['wrmbs']
			except:
				print 'Time : ', xtime[time_count-1] , ' -- VM :',vms[j], ' -- No VBD :', no_vbd, ' & j =' , j , ' & vms[0] =',vms[0] , ' & vms[1] =', vms[1]
				print "myDataList[i]['Name'] is " , self.myDataList[i]['Name'] , " & self.myDataList[j]['vbd'] is ", self.myDataList[i]['vbd'] 
				return
			#print xtime[time_count-1], ' : ', vms[j] , ' vbd ', no_vbd , ' RD speed =' , vbd_rd[time_count-1][j][no_vbd]
			#print xtime[time_count-1], ' : ', vms[j] , ' vif ', no_vbd , ' WR speed =' , vbd_wr[time_count-1][j][no_vbd]
			no_vbd = no_vbd + 1
			if num_vbds[j] < no_vbd:
				num_vbds[j] = no_vbd
						
			#print 'time_count =', time_count-1, 'j = ',j , 'No. of Vifs:', num_vifs[j] , 'RX = ',vif_rx[time_count-1][j][no_vif-1], ' KB/s  & TX = ', vif_tx[time_count-1][j][no_vif-1], ' KB/s'
			i = i + 1
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		
		if xtime[0].date() != xtime[len(xtime)-1].date():
			myFmt = mdates.DateFormatter('%d-%b %H:%M:%S')
		else:
			myFmt = mdates.DateFormatter('%H:%M:%S')
		
		self.axes.xaxis.set_major_formatter(myFmt)
		y = []
		j = 0
		i = 0
		k = 0
		rd = []
		wr = []
		#print num_vms
		
		x1 = np.array(xtime)

		while j < num_vms:
			del rd[0:len(rd)]
			del wr[0:len(wr)]
			rd = []
			wr = []
			k = 0
			while k < num_vbds[j]:
				del y[0:len(y)]
				y = []			
				i = 0
				while i < time_count:
					y.append((vbd_rd[i][j][k] + vbd_wr[i][j][k])*8)
					i = i+1
				#print '\nVM Name', vms[j] , y
				#print 'xtime length=', len(xtime), '  rx length =', len(rx) , '  tx length =',len(tx)
				print 'xtime length=', len(xtime), '  Y length =', len(y)
				#self.axes.plot(xtime,rx,label=vms[j] + ' vif' + str(k)+ ' RX')
				#self.axes.plot(xtime,tx,label=vms[j] + ' vif' + str(k) + ' TX')
				y1 = np.array(y)
				#print 'x1 len =', len(x1), ' y1 len =', len(y1)
				self.axes.plot(x1,y1, '-+' ,linewidth=2.0,  label=vms[j] + ' vbd' + str(k))
				k = k+1
			j = j + 1
				
		
		legend = self.axes.legend(bbox_to_anchor=(1, 1), loc=1, borderaxespad=0.5)
		#loc='upper right', shadow=True)
		#self.axes.set_xlabel('Date/time')
		self.axes.grid(True)
		self.axes.set_ylabel('------ MB/s (RD + WR) ------>')
		self.figure.autofmt_xdate()
		self.canvas.draw()
		

	def Network_DataPopulate(self, vmslist=[], sel_bridge=[]):
		# Open database connection
		
		#db = MySQLdb.connect("10.176.255.55","xenmon","xenmon123","xen_monitor" )
		db = MySQLdb.connect(self.DB_IP, self.DB_User, self.DB_Password, self.DB_Name)

		# prepare a cursor object using cursor() method
		cursor = db.cursor()
		dlg = wx.MessageDialog(self, 'DB Connected! Please wait while we are fetching data...', 'Patience...', wx.OK|wx.ICON_INFORMATION)
		dlg.ShowModal()
		dlg.Destroy()
		
		sql = "SELECT * FROM network_stat where time > '" + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		sql_conditions = " and ("
		k = 0
		while k < len(vmslist):
			if k > 0:
				sql_conditions = sql_conditions + " or "	
			sql_conditions = sql_conditions + " name = '" + vmslist[k] + "'"
			k = k + 1
		
		sql_conditions = sql_conditions + ")"
		
		if (len(sel_bridge) > 0):
			sql_conditions = " and ("
			k = 0
			while k < len(sel_bridge):
				if k > 0:
					sql_conditions = sql_conditions + " or "
				sql_conditions = sql_conditions + " bridge = '" + sel_bridge[k] + "'"
				k = k + 1
				
			sql_conditions = sql_conditions + ")"
		
			
		if k > 0:
			sql = sql + sql_conditions
		print 'SQL Query is : ', sql
				
		self.myDataList = []
		
		# Execute the SQL command
		cursor.execute(sql)
		# Fetch all the rows in a list of lists.
		results = cursor.fetchall()
		i = 0
		for row in results:
			time = row[0]
			name = row[1]
			vif = row[2]
			bridge = row[3]
			if row[4] >= 0 and row[4] < 12000000:
				rxmbs = row[4]/1000
			else:
				rxmbs = 0
			
			if row[5] >= 0 and row[5] < 12000000:
				txmbs = row[5]/1000
			else:
				txmbs = 0
			#print "Time=%s,name=%s,vcpu=%d,phycpu=%s,pcent_usage=%d" % (time, name, vcpu, phycpu, pcent_usage)
			#if  < 101:
			self.myDataList.append({'Time':time, 'Name':name, 'vif':vif,'bridge':bridge, 'rxmbs':rxmbs, 'txmbs':txmbs})
			i = i+1
		
		sql = "Select distinct name,vif FROM network_stat where time > '" + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		if k > 0:
			sql = sql + sql_conditions
			print 'Distinct SQL statement', sql
			
		cursor.execute(sql)
		results1 = cursor.fetchall()
		prev_name = ''
		self.all_vifs = [[]]
		j = -1
		for row1 in results1:
			if prev_name != row1[0]:
				prev_name = row1[0]
				self.all_vifs.append([])
				j = j + 1
			self.all_vifs[j].append(0)
			print prev_name , ' :' , self.all_vifs[j]
				
		db.close()		
		if i == 0:
			dlg = wx.MessageDialog(self, 'No data captured in the DB for the said time period...', 'Ooopps...', wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
			return
		
		self.grid1.ClearGrid()
		
		current_cols, new_cols = (self.grid1.GetNumberCols(), 7)
		if new_cols < current_cols:
        #- Delete rows:
			self.grid1.DeleteCols(0, current_cols - new_cols, True)

		if new_cols > current_cols:
        #- append rows:
			self.grid1.AppendCols(new_cols - current_cols)
			
		current_rows, new_rows = (self.grid1.GetNumberRows(), i)
		if new_rows < current_rows:
        #- Delete rows:
			self.grid1.DeleteRows(0, current_rows - new_rows , True)

		if new_rows > current_rows:
        #- append rows:
			self.grid1.AppendRows(new_rows - current_rows)		
		
		self.grid1.SetColLabelValue(0, "Time                                 ")
		self.grid1.SetColLabelValue(1, "VM Name       ")
		self.grid1.SetColLabelValue(2, "Vif   ")
		self.grid1.SetColLabelValue(3, "Bridge     ")
		self.grid1.SetColLabelValue(4, "RX Mb/s")
		self.grid1.SetColLabelValue(5, "TX Mb/s")
		self.grid1.SetColLabelValue(6, "Total usage Mb/s")
		
		#print i
		#print 
		j=0
		while j<i:
			self.grid1.SetCellValue(j,0, str(self.myDataList[j]['Time']))
			self.grid1.SetCellValue(j,1, self.myDataList[j]['Name'])
			self.grid1.SetCellValue(j,2, str(self.myDataList[j]['vif']))
			self.grid1.SetCellValue(j,3, self.myDataList[j]['bridge'])
			rx=0
			tx=0
			if self.myDataList[j]['rxmbs'] >= 0 and self.myDataList[j]['rxmbs'] < 12000000:
				rx = self.myDataList[j]['rxmbs'] * 8
				
			self.grid1.SetCellValue(j,4, str(rx))							
							
			if 	self.myDataList[j]['txmbs'] >= 0 and self.myDataList[j]['txmbs'] < 12000000:
				tx = self.myDataList[j]['txmbs'] * 8
				
			self.grid1.SetCellValue(j,5, str(tx))
						
			self.grid1.SetCellValue(j,6,str(rx + tx))
				
			j=j+1
				
		self.grid1.AutoSizeColumn(0,)
		self.grid1.AutoSizeColumn(1,)
		self.grid1.AutoSizeColumn(2,)
		self.grid1.AutoSizeColumn(3,)
		self.grid1.AutoSizeColumn(4,)
		self.grid1.AutoSizeColumn(5,)
		self.grid1.AutoSizeColumn(6,)
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		#x = [ 0 , 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
		#y = [ 10, 2, 5, 6, 4 , 5 , 7, 4, 7, 5, 20, 6, 8, 30 , 9, 7, 8, 9, 2, 7, 5, 8, 9 ,7, 5, 6]
		#self.axes.plot(x, y)
		#self.canvas.draw()
		
		self.PlotGraph_Network_stat(i)
		
	
	def PlotGraph_Network_stat(self, num_elements):
		time_count=0
		prev_time = ''
		prev_name = ''
		i=0
		j=0
		match=0
		sm=0
		avg_count=0
		num_vms = 0
		
		xtime = []
		vms = []
		vif_rx = [[]]
		vif_tx = [[]]
		num_vifs= []
		#
		# Extracting DB contents into a 2-dimentional array to retrieve each VM wise Avg %cpu usage such as 
		# a[0][1]=40%   --> here [0] represents the first time interval and [1] represents the Guest VM
		# the range would be like a[0 - (number of samples-1)][0 - (num of VMs -1)]
		#
				
		while i < num_elements:
			cur_time = str(self.myDataList[i]['Time'])
						
			if  cur_time != prev_time:
				time_count = time_count +1
				prev_time = cur_time
				xtime.append(self.myDataList[i]['Time'])
				#print xtime[time_count-1]
				sm = 0
				avg_count = 0
				#j = 0
				vif_rx.append([])
				vif_tx.append([])
				no_vif=0
								
				k=0
				while k < len(self.all_vifs):
					vif_rx[time_count-1].append([])
					vif_tx[time_count-1].append([])
					m=0
					while m < len(self.all_vifs[k]):
						vif_rx[time_count-1][k].append(0)
						vif_tx[time_count-1][k].append(0)
						m = m + 1
					k = k + 1
										
			if self.myDataList[i]['Name'] != prev_name:
				avg_count=0
				sm=0
				match=0
				j = 0
				no_vif=0
				while j < num_vms:
					if self.myDataList[i]['Name'] == vms[j]:
						match = 1
						prev_name = self.myDataList[i]['Name']
						
						break
					j = j+1	
				num_vifs.append(0)
				if match == 0:
					j = num_vms
					vms.append(self.myDataList[i]['Name'])
					num_vms = num_vms + 1
					#a.append(time_count-1)
					#vif_rx[time_count-1].append([])
					#vif_tx[time_count-1].append([])
					prev_name = self.myDataList[i]['Name']
					num_vifs.append(0)
					
			vif_rx[time_count-1][j][no_vif] = self.myDataList[i]['rxmbs']
			vif_tx[time_count-1][j][no_vif] = self.myDataList[i]['txmbs']
			#print xtime[time_count-1], ' : ', vms[j] , ' vif ', no_vif , ' RX val =' , vif_rx[time_count-1][j][no_vif]
			#print xtime[time_count-1], ' : ', vms[j] , ' vif ', no_vif , ' TX val =' , vif_tx[time_count-1][j][no_vif]
			no_vif = no_vif + 1
			if num_vifs[j] < no_vif:
				num_vifs[j] = no_vif
			
			
			#print 'time_count =', time_count-1, 'j = ',j , 'No. of Vifs:', num_vifs[j] , 'RX = ',vif_rx[time_count-1][j][no_vif-1], ' KB/s  & TX = ', vif_tx[time_count-1][j][no_vif-1], ' KB/s'
			i = i + 1
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		
		if xtime[0].date() != xtime[len(xtime)-1].date():
			myFmt = mdates.DateFormatter('%d-%b %H:%M:%S')
		else:
			myFmt = mdates.DateFormatter('%H:%M:%S')
		
		self.axes.xaxis.set_major_formatter(myFmt)
		
		y = []
		j = 0
		i = 0
		k = 0
		rx = []
		tx = []
		#print num_vms
		
		x1 = np.array(xtime)

		while j < num_vms:
			del rx[0:len(rx)]
			del tx[0:len(tx)]
			rx = []
			tx = []
			k = 0
			while k < num_vifs[j]:
				del y[0:len(y)]
				y = []			
				i = 0
				while i < time_count:
					y.append((vif_rx[i][j][k] + vif_tx[i][j][k])*8)
					i = i+1
				#print '\nVM Name', vms[j] , y
				#print 'xtime length=', len(xtime), '  rx length =', len(rx) , '  tx length =',len(tx)
				print 'xtime length=', len(xtime), '  Y length =', len(y)
				#self.axes.plot(xtime,rx,label=vms[j] + ' vif' + str(k)+ ' RX')
				#self.axes.plot(xtime,tx,label=vms[j] + ' vif' + str(k) + ' TX')
				y1 = np.array(y)
				#print 'x1 len =', len(x1), ' y1 len =', len(y1)
				self.axes.plot(x1,y1, '-+' ,linewidth=2.0,  label=vms[j] + ' vif' + str(k))
				k = k+1
			j = j + 1				
		
		legend = self.axes.legend(bbox_to_anchor=(1, 1), loc=1, borderaxespad=0.5)
		#loc='upper right', shadow=True)
		#self.axes.set_xlabel('Date/time')
		self.axes.grid(True)
		self.axes.set_ylabel('------ Mb/s (rx + tx) ------>')
		self.figure.autofmt_xdate()
		self.canvas.draw()
		
		
	def vCPU_DataPopulate(self, vmslist=[]):
		# Open database connection
		i = 0
		#db = MySQLdb.connect("10.176.255.55","xenmon","xenmon123","xen_monitor" )
		db = MySQLdb.connect(self.DB_IP, self.DB_User, self.DB_Password, self.DB_Name)

		# prepare a cursor object using cursor() method
		cursor = db.cursor()
		dlg = wx.MessageDialog(self, 'DB Connected! Please wait while we are fetching data...', 'Patience...', wx.OK|wx.ICON_INFORMATION)
		dlg.ShowModal()
		dlg.Destroy()
		
		sql = "SELECT * FROM cpu_stat where time > '"  + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		sql_conditions = " and ("
		k = 0
		while k < len(vmslist):
			if k > 0:
				sql_conditions = sql_conditions + " or "	
			sql_conditions = sql_conditions + " name = '" + vmslist[k] + "'"
			k = k + 1
		
		sql_conditions = sql_conditions + ")"
		if k > 0:
			sql = sql + sql_conditions
		print 'SQL Query is : ', sql
		
		
		self.myDataList = []

		# Execute the SQL command
		cursor.execute(sql)
		# Fetch all the rows in a list of lists.
		results = cursor.fetchall()
		for row in results:
			time = row[0]
			name = row[1]
			vcpu = row[2]
			phycpu = row[3]
			pcent_usage = row[4]
			#print "Time=%s,name=%s,vcpu=%d,phycpu=%s,pcent_usage=%d" % (time, name, vcpu, phycpu, pcent_usage)
			if pcent_usage < 101:
				self.myDataList.append({'Time':time, 'Name':name, 'vcpu':vcpu, 'phycpu':phycpu, 'pcent_usage':pcent_usage})
				i = i+1

		
		sql = "Select distinct name,vcpu FROM cpu_stat where time > '"  + self.txt_fromdate.GetValue() + "' and time < '" + self.txt_todate.GetValue() + "'" 
		if k > 0:
			sql = sql + sql_conditions
		
		cursor.execute(sql)
		results1 = cursor.fetchall()
		prev_name = ''
		self.all_vcpus = [[]]
		j = -1
		for row1 in results1:
			if prev_name != row1[0]:
				prev_name = row1[0]
				self.all_vcpus.append([])
				j = j + 1
			self.all_vcpus[j].append(0)
			print prev_name , ' :' , self.all_vcpus[j]
			
		db.close()
		
		if i == 0:
			dlg = wx.MessageDialog(self, 'No data captured in the DB for the said time period...', 'Ooopps...', wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
			return
		
		self.grid1.ClearGrid()
		
		current_cols, new_cols = (self.grid1.GetNumberCols(), 5)
		if new_cols < current_cols:
        #- Delete rows:
			self.grid1.DeleteCols(0, current_cols - new_cols, True)

		if new_cols > current_cols:
        #- append rows:
			self.grid1.AppendCols(new_cols - current_cols)
			
		current_rows, new_rows = (self.grid1.GetNumberRows(), i)
		if new_rows < current_rows:
        #- Delete rows:
			self.grid1.DeleteRows(0, current_rows - new_rows , True)

		if new_rows > current_rows:
        #- append rows:
			self.grid1.AppendRows(new_rows - current_rows)		
			
		self.grid1.SetColLabelValue(0, "Time                                 ")
		self.grid1.SetColLabelValue(1, "VM Name       ")
		self.grid1.SetColLabelValue(2, "vCPU   ")
		self.grid1.SetColLabelValue(3, "PhyCPU    ")
		self.grid1.SetColLabelValue(4, "Util%  ")
			
		j=0
		while j<i:
			self.grid1.SetCellValue(j,0, str(self.myDataList[j]['Time']))
			self.grid1.SetCellValue(j,1, self.myDataList[j]['Name'])
			self.grid1.SetCellValue(j,2, str(self.myDataList[j]['vcpu']))
			self.grid1.SetCellValue(j,3, str(self.myDataList[j]['phycpu']))
			self.grid1.SetCellValue(j,4, str(self.myDataList[j]['pcent_usage']))
			j=j+1
				
		self.grid1.AutoSizeColumn(0,)
		self.grid1.AutoSizeColumn(1,)
		self.grid1.AutoSizeColumn(2,)
		self.grid1.AutoSizeColumn(3,)
		self.grid1.AutoSizeColumn(4,)
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		x = [ 0 , 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
		y = [ 10, 2, 5, 6, 4 , 5 , 7, 4, 7, 5, 20, 6, 8, 30 , 9, 7, 8, 9, 2, 7, 5, 8, 9 ,7, 5, 6]
		#self.axes.plot(x, y)
		#self.canvas.draw()
		
		if len(vmslist) > 0:
			self.PlotGraph_CPU(i)
		else:
			self.PlotGraph_Avg_CPU(i)
			

	def PlotGraph_CPU(self, num_elements):
		
		time_count=0
		prev_time = ''
		prev_name = ''
		i=0
		j=0
		match=0
		sm=0
		vcpu_count=0
		num_vms = 0
		num_vcpus = []
		
		xtime = []
		vms = []
		vcpu = [[[]]]
		#
		# Extracting DB contents into a 2-dimentional array to retrieve each VM wise Avg %cpu usage such as 
		# a[0][1]=40%   --> here [0] represents the first time interval and [1] represents the Guest VM
		# the range would be like a[0 - (number of samples-1)][0 - (num of VMs -1)]
		#
		while i < num_elements:
			cur_time = str(self.myDataList[i]['Time'])
						
			if  cur_time != prev_time:
				time_count = time_count +1
				prev_time = cur_time
				xtime.append(self.myDataList[i]['Time'])
				#print xtime[time_count-1]
				sm = 0
				vcpu_count = 0
				vcpu.append([])				
				k=0
				no_of_vms = len(self.all_vcpus)
				while k < no_of_vms:
					vcpu[time_count-1].append([])
					m=0
					no_of_vcpus = len(self.all_vcpus[k])
					while m < no_of_vcpus:
						vcpu[time_count-1][k].append(0)
						m = m + 1
					k = k + 1
		
			if self.myDataList[i]['Name'] != prev_name:
				vcpu_count=0
				sm=0
				match=0
				j = 0
				while j < num_vms:
					if self.myDataList[i]['Name'] == vms[j]:
						match = 1
						prev_name = self.myDataList[i]['Name']
						break
					j = j+1	
					
				if match == 0:
					j = num_vms
					vms.append(self.myDataList[i]['Name'])
					num_vms = num_vms + 1
					prev_name = self.myDataList[i]['Name']
					num_vcpus.append(0)
					
			vcpu[time_count-1][j][vcpu_count] = self.myDataList[i]['pcent_usage']
			
			vcpu_count = vcpu_count + 1
			if num_vcpus[j] < vcpu_count:
				num_vcpus[j] = vcpu_count
			#print 'time_count =', time_count-1, 'j = ',j ,a[time_count-1][j]
			i = i + 1
			
		#print the values to confirm		
		i = 0
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		
		if xtime[0].date() != xtime[len(xtime)-1].date():
			myFmt = mdates.DateFormatter('%d-%b %H:%M:%S')
		else:
			myFmt = mdates.DateFormatter('%H:%M:%S')
		
		self.axes.xaxis.set_major_formatter(myFmt)

		j = 0
		i = 0
		y = []
		print num_vms
		
		while j < num_vms:
			k = 0
			while k < num_vcpus[j]:
				del y[0:len(y)]
				y = []
				i = 0
				while i < time_count:
					y.append((vcpu[i][j][k]))
					i = i + 1
					
				print 'xtime length=', len(xtime), 'y length =',len(y)
				self.axes.plot(xtime,y,'-+', label=vms[j] + ' vcpu:' + str(k))
				k = k + 1
			j = j + 1	
			'''
		while j < num_vms:
			del y1[0:len(y1)]
			y1 = []
			i = 0
			while i < time_count:
				y1.append(a[i][j])
				i = i+1				
			
			print 'xtime length=', len(xtime), 'y1 length =',len(y1)
			self.axes.plot(xtime,y1,label=vms[j])
			j = j + 1
		'''
		legend = self.axes.legend(bbox_to_anchor=(1, 1), loc=1, borderaxespad=0.)
		
		self.axes.set_ylabel('-------- CPU Util % ------->')
		self.figure.autofmt_xdate()
		self.canvas.draw()
		
	def PlotGraph_Avg_CPU(self, num_elements):
		
		time_count=0
		prev_time = ''
		prev_name = ''
		i=0
		j=0
		match=0
		sm=0
		avg_count=0
		num_vms = 0
		
		xtime = []
		vms = []
		a = [[]]
		#
		# Extracting DB contents into a 2-dimentional array to retrieve each VM wise Avg %cpu usage such as 
		# a[0][1]=40%   --> here [0] represents the first time interval and [1] represents the Guest VM
		# the range would be like a[0 - (number of samples-1)][0 - (num of VMs -1)]
		#
		while i < num_elements:
			cur_time = str(self.myDataList[i]['Time'])
						
			if  cur_time != prev_time:
				time_count = time_count +1
				prev_time = cur_time
				xtime.append(self.myDataList[i]['Time'])
				#print xtime[time_count-1]
				sm = 0
				avg_count = 0
				a.append([])
				k=0
				while k < len(self.all_vcpus):
					a[time_count-1].append(0)
					k = k + 1
		
			if self.myDataList[i]['Name'] != prev_name:
				avg_count=0
				sm=0
				match=0
				j = 0
				while j < num_vms:
					if self.myDataList[i]['Name'] == vms[j]:
						match = 1
						prev_name = self.myDataList[i]['Name']
						break
					j = j+1	
					
				if match == 0:
					j = num_vms
					vms.append(self.myDataList[i]['Name'])
					num_vms = num_vms + 1
					#a.append(time_count-1)
					#a[time_count-1].append(0)
					prev_name = self.myDataList[i]['Name']
					#print vms[j]					
					
			avg_count = avg_count + 1
			sm = sm + self.myDataList[i]['pcent_usage']
			a[time_count-1][j]= sm/avg_count
			#print 'time_count =', time_count-1, 'j = ',j ,a[time_count-1][j]
			i = i + 1
			
		#print the values to confirm		
		i = 0
		
		self.axes.hold(False)
		self.axes.cla()
		self.axes.hold(True)
		
		if xtime[0].date() != xtime[len(xtime)-1].date():
			myFmt = mdates.DateFormatter('%d-%b %H:%M:%S')
		else:
			myFmt = mdates.DateFormatter('%H:%M:%S')
		
		self.axes.xaxis.set_major_formatter(myFmt)

		j = 0
		i = 0
		y1 = []
		print num_vms
		
		while j < num_vms:
			del y1[0:len(y1)]
			y1 = []
			i = 0
			while i < time_count:
				y1.append(a[i][j])
				i = i+1				
			
			print 'xtime length=', len(xtime), 'y1 length =',len(y1)
			self.axes.plot(xtime,y1, '-+', label=vms[j])
			j = j + 1
		
		legend = self.axes.legend(bbox_to_anchor=(1, 1), loc=1, borderaxespad=0.)
		
		self.axes.set_ylabel('------ Avg CPU Util % ------>')
		self.figure.autofmt_xdate()
		self.canvas.draw()
		
	def populate_ctree(self):
		
		root = self.ctree.AddRoot('Component')
		vm = self.ctree.AppendItem(root, 'Virtual Machines')
		bridge = self.ctree.AppendItem(root, 'Bridge Devices')
		disk = self.ctree.AppendItem(root, 'Phy Disks')
		
		# Fetch the list of all available Guest VMs from the DB :
		vms = []
		bridges = []
		phy_disk = []
		num_vms = 0
		num_bridge = 0
		num_phydisk = 0
		
	#	self.DB_IP = "10.176.255.55"
	#	self.DB_Name = "xen_monitor"
	#	self.DB_User = "xenmon"
	#	self.DB_Password = "xenmon123"
		
		print '\n Attempting DB Connection to ', self.DB_IP , ' !  Please wait...\n\n'
		
		db = MySQLdb.connect(self.DB_IP, self.DB_User, self.DB_Password, self.DB_Name)
		cursor = db.cursor()
		
		sql = "SELECT distinct(name) from cpu_stat"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			vms.append(row[0])
			#print 'VM Name:', vms[num_vms]
			vm_details = self.ctree.AppendItem(vm,vms[num_vms])
			num_vms = num_vms + 1
			
			self.ctree.AppendItem(vm_details,'vCPUs')						
			if row[0] != 'Domain-0':	
				self.ctree.AppendItem(vm_details,'Networks')
				self.ctree.AppendItem(vm_details,'Virtual Disks')			
		
		sql = "SELECT distinct name,backend from vbd_stat"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			phy_disk.append(row[1])
			#print 'phy disk/image file :', phy_disk[num_phydisk]
			self.ctree.AppendItem(disk, phy_disk[num_phydisk] + '(' + row[0] + ')' )
			num_phydisk = num_phydisk + 1
		
		sql = "SELECT distinct(bridge) from network_stat"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			bridges.append(row[0])
			#print 'bridge name:', bridge[num_bridge]
			self.ctree.AppendItem(bridge ,bridges[num_bridge])
			num_bridge = num_bridge + 1

		db.close()
		
	def InitUI(self):
		
		self.DB_IP = "10.176.255.55"
		self.DB_Name = "xen_monitor"
		self.DB_User = "xenmon"
		self.DB_Password = "xenmon123"
		
		#panel = wx.Panel(self)
		vbox = wx.BoxSizer(wx.VERTICAL)
		
		hbox1 = wx.BoxSizer(wx.HORIZONTAL)
		st1 = wx.StaticText(self, label='From Date/time')
		st2 = wx.StaticText(self, label='To Date/time')
		self.txt_fromdate = wx.TextCtrl(self,size=(150,25), name='From Date & Time YYYY-MM-DD HH:MM:SS'  )

		#txt_fromdate = wx.DatePickerCtrl(name='datePickerCtrl1', dt=wx.DateTime_Now() , parent=self,  size=wx.Size(200, 25))
		#txt_fromdate.SetValue(wx.DateTime_Now())
		self.txt_fromdate.Bind(wx.EVT_MOTION, self.OnMouseMotion)
		self.txt_todate =  wx.TextCtrl(self,size=(150,25))
		
		today = datetime.now()
		self.txt_todate.SetValue(today.strftime('%Y-%m-%d %H:%M:%S'))
		yesterday = today - timedelta(days=1)
		
		self.txt_fromdate.SetValue(yesterday.strftime('%Y-%m-%d %H:%M:%S'))
		
		info = ['vCPU', 'Network', 'Disk']
		self.cb = wx.ComboBox(self, pos=(50, 30), choices=info, style=wx.CB_READONLY, size=(180,25))
		self.combo_selected = 0
		#Combo box event add
		self.cb.Bind(wx.EVT_COMBOBOX, self.OnSelect)
		
		# Date control
		#self.dateCtrl = wx.DatePickerCtrl(self, -1)

		#create time control
		#self.timeCtrl = wx.TimePickerCtrl(self,style=TP_DEFAULT)
		#display_seconds=False,fmt24hr=False, id=-1, name='timeCtrl', style=0,useFixedWidthFont=True, value=datetime.now().strftime('%X'), pos = (250,70))
		
		self.button = wx.Button(self, 1, label='Go...' , size=(50,25), style=wx.BU_LEFT|wx.SUNKEN_BORDER)
		self.button.Bind(wx.EVT_BUTTON, self.OnGo)
		#, validator=DefaultValidator, name=ButtonNameStr) 
		
		hbox1.Add(st1, flag=wx.RIGHT, border=8)
		hbox1.Add(self.txt_fromdate, flag=wx.LEFT, border=8)
		hbox1.Add(st2, flag=wx.LEFT, border=8)
		hbox1.Add(self.txt_todate, flag=wx.LEFT, border=8)
				
		hbox1.Add(self.cb,flag=wx.LEFT, border=20)
		#hbox1.Add(self.dateCtrl,flag=wx.LEFT, border=10)
		hbox1.Add(self.button,flag=wx.LEFT, border=20)
		#hbox1.Add(self.timeCtrl,flag=wx.LEFT, border=10)
		
		vbox.Add(hbox1,flag=wx.LEFT|wx.RIGHT|wx.TOP, border=10)
		vbox.Add((-1, 10))
		
		hbox2 = wx.BoxSizer(wx.HORIZONTAL)
		
		self.ctree = wx.TreeCtrl(self, 1, wx.DefaultPosition, (200, 520), style=wx.TR_MULTIPLE|wx.TR_HAS_BUTTONS|wx.TR_HIDE_ROOT|wx.TR_LINES_AT_ROOT)
		#comptree = component_tree(self, 1, wx.DefaultPosition, (200, 520),wx.TR_HIDE_ROOT|wx.TR_HAS_BUTTONS)
		self.populate_ctree()
		
		self.figure = Figure()
		self.axes = self.figure.add_subplot(111)
		
		x = [ 0 , 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
		y = [ 5, 6, 5, 6, 4 , 5 , 7, 4, 7, 5, 10, 6, 8, 10 , 9, 7, 8, 10, 6, 7, 5, 8, 9 ,7, 5, 6]
		x1 = [ 0 , 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
		y1 = [ 6, 8, 9, 6, 5 , 7 , 8, 9, 10, 12, 7, 9, 8, 9 , 8, 6, 7, 6, 9, 8, 8, 9, 10 ,9, 5, 6]
		self.figure.add_subplot(111)
		#self.axes.SubplotParams(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
		self.figure.tight_layout(renderer=None, pad=1, h_pad=None, w_pad=None, rect=None)
		self.axes.hold(True)
		self.axes.plot(x, y)
		self.axes.plot(x1,y1)
		self.canvas = FigureCanvas(self, wx.ID_ANY, self.figure)
		self.canvas.draw()
		
		#pixels = tuple( self.GetClientSize() )
		pixels = self.GetClientSize()
		pixels[0] = pixels[0] - 200
		pixels[1] = pixels[1] - 300
		#self.SetSize( pixels )
		self.canvas.SetSize( pixels )
		self.figure.set_size_inches( float( pixels[0] )/self.figure.get_dpi(), float( pixels[1] )/self.figure.get_dpi() )
		
		#Tool bar
		self.toolbar = NavigationToolbar2Wx(self.canvas)
		#self.toolbar.SetSize(20, 50)
		self.toolbar.Realize()
		
		vbox_internal = wx.BoxSizer(wx.VERTICAL)
		vbox_internal.Add(self.toolbar,0,wx.TOP|wx.LEFT)
		vbox_internal.Add(self.canvas,1,wx.LEFT|wx.TOP|wx.EXPAND)

		#vbox_internal.Fit(self)

		hbox2.Add(self.ctree,0, flag=wx.LEFT|wx.EXPAND,border=10)
		hbox2.Add(vbox_internal, 1, wx.LEFT | wx.TOP | wx.EXPAND)

		vbox.Add(hbox2,flag=wx.LEFT|wx.RIGHT|wx.TOP)
		
		hbox3 = wx.BoxSizer(wx.HORIZONTAL)
		
		self.grid1 = wx.grid.Grid(name='grid1', parent=self, pos=wx.Point(16, 64), size=wx.Size(776, 208), style=0)
		self.grid1.SetAutoLayout(False)
		self.grid1.CreateGrid(12,5)
		#self.grid1.SetColSize(3, 200)
		#self.grid1.SetRowSize(4, 45)

		#self.vCPU_DataPopulate()
		j=0
		hbox3.Add(self.grid1, 1, flag=wx.LEFT|wx.EXPAND, border=10)

		vbox.Add(hbox3,1, flag=wx.LEFT|wx.EXPAND,border=10)
		self.SetSizer(vbox)
		self.Fit()
		self.Show()
		self.Refresh()
	
	def OnGo(self,evt):
					
		if self.combo_selected == 1:
			print 'Selected item in Combo box', self.cb.GetCurrentSelection()
			item = self.cb.GetCurrentSelection()
			if item == 0:
				self.vCPU_DataPopulate()
			elif item == 1:
				self.Network_DataPopulate()
			elif item == 2:
				self.VBD_DataPopulate()
			self.combo_selected = 0
			return
			
		#sel = self.ctree.GetItemText(self.ctree.GetSelections())
		sel_vcpus = []
		sel_net = []
		sel_disk = []
		sel_bridge = []
		sel_phydisk = []
		for i in self.ctree.GetSelections():
			parent = self.ctree.GetItemParent(i)
			grand_parent = self.ctree.GetItemParent(parent)
			selection_text = self.ctree.GetItemText(i)
			
			if selection_text == 'vCPUs':
				sel_vcpus.append(self.ctree.GetItemText(parent))
							
			elif selection_text == 'Networks':
				sel_net.append(self.ctree.GetItemText(parent))
			
			elif selection_text == 'Virtual Disks':
				sel_disk.append(self.ctree.GetItemText(parent))
			
			elif self.ctree.GetItemText(parent) == 'Bridge Devices':
				sel_bridge.append(selection_text)
				
			elif self.ctree.GetItemText(parent) == 'Phy Disks':
				sel_phydisk.append(selection_text)
			
				
		if 	len(sel_vcpus) > 0 and len(sel_net) > 0 or len(sel_vcpus) > 0 and len(sel_disk) > 0 or len(sel_disk) > 0 and len(sel_net) > 0:
			dlg = wx.MessageDialog(self, 'Select only one type of Data \nSuch as, vCPU Info. from multiple Guest VMs ', 'Incorrect selection...', wx.OK|wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
		elif len(sel_vcpus) > 0:
			self.vCPU_DataPopulate(sel_vcpus)
			
		elif len(sel_net) > 0:
			self.Network_DataPopulate(sel_net,sel_bridge)
						
		elif len(sel_bridge) > 0:
			self.Network_DataPopulate(sel_net,sel_bridge)

		elif len(sel_disk) > 0 or len(sel_phydisk) > 0:
			sel_diskname = []
			k=0
			while k < len(sel_phydisk):
				sel_diskname.append('')
				sel_diskname[k] , tmp, b = sel_phydisk[k].partition('(')
				print sel_diskname[k]
				k = k + 1
			self.VBD_DataPopulate(sel_disk,sel_diskname)			
			
			
	def OnSelect(self,evt):
		item = evt.GetSelection()
		print 'Selected item', self.cb.GetCurrentSelection()
		print item
		self.combo_selected = 1
			

	def OnMouseMotion(self, evt):
		#print 'abc', evt
		tip = wx.ToolTip(self.txt_fromdate.GetName())
		self.txt_fromdate.SetToolTip(tip)


if __name__ == '__main__':
    app = wx.App()
    UI_init(None, title=' Xen Monitor                                                                 ')
    app.MainLoop()
