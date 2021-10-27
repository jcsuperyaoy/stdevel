#!/usr/bin/env python
# -*- coding: utf-8 -*-

# satprep_diff.py - a script for creating patch
# diff reports
#
# 2015 By Christian Stankowic
# <info at stankowic hyphen development dot net>
# https://github.com/stdevel
#

import logging
from optparse import OptionParser, OptionGroup
import ConfigParser
import sys
import os
import stat
import difflib
import time
import csv
import string
import datetime

#define logger
LOGGER = logging.getLogger('satprep_diff')
vlogInvalid=False

#TODO: delete original snapshots after creating delta option
#TODO: use pre-existing delta CSV instead of creating one (e.g. for testing purposes)



class LaTeXTemplate(string.Template):
	delimiter = "%%"

def parse_options(args=None):
	if args is None:
		args = sys.argv
	
        #define usage, description, version and load parser
	usage = "usage: %prog [options] snapshot.csv snapshot.csv"
        desc='''%prog is used to create patch diff reports of systems managed with Spacewalk, Red Hat Satellite and SUSE Manager. The script needs TeXlive/LaTeX to create PDF reports. Defining your own templates is possible - the default template needs to be located in the same directory like this script.
		
		Checkout the GitHub page for updates: https://github.com/stdevel/satprep'''
        parser = OptionParser(usage=usage, description=desc, version="%prog version 0.3")
        #define option groups
        genOpts = OptionGroup(parser, "Generic Options")
        repOpts = OptionGroup(parser, "Report Options")
        parser.add_option_group(genOpts)
        parser.add_option_group(repOpts)
	
	#GENERIC OPTIONS
        #-d / --debug
        genOpts.add_option("-d", "--debug", dest="debug", default=False, action="store_true", help="enable debugging outputs (default: no)")
	#-b / --pdflatex-binary
	genOpts.add_option("-b", "--pdflatex-binary", action="store", type="string", dest="pathPdflatex", default="/usr/bin/pdflatex", metavar="PATH", help="location for the pdflatex binary (default: /usr/bin/pdflatex)")
	
	#REPORT OPTIONS
	#-t / --template
	repOpts.add_option("-t", "--template", dest="template", default="default", metavar="FILE", help="defines the template which is used to generate the report (default: cwd/default.tex)")
        #-o / --output
        repOpts.add_option("-o", "--output", action="store", type="string", dest="output", default="foobar", help="define report filename. (default: errata-diff-report-Ymd.csv)", metavar="FILE")
	#-u / --use-delta-from
	#repOpts.add_option("-u", "--use-delta-from", action="store", type="string", dest="deltafile", default="", metavar="FILE", help="defines previously created delta file - useful if you don't want to re-create the delta")
	#TODO: implement
	#-n / --no-host-reports
	repOpts.add_option("-n", "--no-host-reports", action="store_true", default=False, dest="noHostReports", help="only create delta CSV report and skip creating host reports (default: no)")
	#-x / --preserve-tex
	repOpts.add_option("-x", "--preserve-tex", action="store_true", default=False, dest="preserveTex", help="keeps the TeX files after creating the PDF reports (default: no)")
	#-p / --page-orientation
	repOpts.add_option("-p", "--page-orientation", action="store", type="choice", dest="pageOrientation", default="landscape", metavar="[landscape|potrait]", choices=["landscape","potrait"], help="defines the orientation of the PDF report (default: landscape)")
	#-i / --image
	repOpts.add_option("-i", "--image", action="store", type="string", dest="logoImage", metavar="FILE", help="defines a different company logo")
	#-c / --csv
	#repOpts.add_option("-c", "--csv", action="store", type="string", dest="csvReport", metavar="FILE", help="uses a pre-existing CSV delta report")
	#TODO: implement
	#-f / --footer
	repOpts.add_option("-f", "--footer", action="store", type="string", default="", dest="footer", metavar="STRING", help="changes footer text")
	#-V / --verification-log
	repOpts.add_option("-V", "--verification-log", action="store", default="", dest="verificationLog", metavar="FILE", help="alternate location for verification log (default: $lastSnapshot.vlog)")
	
        #parse and return arguments
        (options, args) = parser.parse_args()
	return (options, args)



def main(options):
	global vlogInvalid
	
	#define folder of this script
	thisFolder = os.path.dirname(os.path.realpath(__file__))
	
        #set some useful default options if not set
        if options.output is 'foobar':
		#default report filename
                options.output = "errata-diff-report-" + time.strftime("%Y%m%d")
	if options.footer == "":
		#default footer
		options.footer = 'This report was automatically generated by \\textbf{satprep} - \href{https://github.com/stdevel/satprep}{https://github.com/stdevel/satprep}'
	#set default logo if none specified or not readable
	if options.logoImage is None or not os.access(os.path.dirname(options.logoImage), os.R_OK):
		if options.logoImage: LOGGER.error("given logo image (" + str(options.logoImage) + ") not readable, using default logo (" + thisFolder + "/default_logo.jpg" + ")")
		if options.debug: LOGGER.debug("Image logo changed to: " + thisFolder + "/default_logo.jpg")
		options.logoImage = thisFolder + "/default_logo.jpg"
	
	#print arguments
	if options.debug: LOGGER.debug("options:"+str(options)+"\nargs: "+str(args))
	
	#check whether two arguments containing (the report files) are given
	#TODO: check if delta report specified with -c / --csv
	if len(args) != 2:
		LOGGER.error("You need to specify two files (snapshot reports!)")
		exit(1)
	
	#check whether report lines are compatible
	file1 = open(args[0], 'r')
	header = file1.readline()
	file2 = open(args[1], 'r')
	if header == file2.readline():
		if options.debug: LOGGER.debug("report headers are compatible!")
		file1.seek(0)
		file2.seek(0)
		#setup field indexes
		headers = header.replace("\n","").replace("\r","").split(";")
		#print header
		repcols = { "hostname" : 666, "ip" : 666, "errata_name" : 666, "errata_type" : 666, "errata_desc" : 666, "errata_date" : 666, "system_owner" : 666, "system_cluster" : 666, "system_virt" : 666, "system_virt_vmname" : 666, "errata_reboot" : 666, "system_monitoring" : 666, "system_monitoring_notes" : 666, "system_monitoring_name" : 666, "system_backup" : 666, "system_backup_notes" : 666, "system_antivir" : 666, "system_antivir_notes" : 666 }
		for name,value in repcols.items():
			try:
				repcols[name] = headers.index(name)
			except ValueError:
				if options.debug: "Unable to find column index for " + name + " so I'm disabling it."
		#print report column indexes
		if options.debug: LOGGER.debug("Report column indexes: " + str(repcols))
	else:
		LOGGER.debug("Your reports are incompatible as they have different columns!")
		exit(1)
	
	#check whether the pdflatex exists
	if not os.access(options.pathPdflatex, os.X_OK):
		LOGGER.error("pdflatex binary (" + options.pathPdflatex + ") not existent or executable!")
		exit(1)
	
	#check whether the template exists
	if os.path.isfile(thisFolder+"/"+options.template+".tex"):
		if options.debug: LOGGER.debug("Template exists!")
		
		#check whether target is writable
		if os.access(os.path.dirname(options.output), os.W_OK) or os.access(os.getcwd(), os.W_OK):
                        if options.debug: LOGGER.debug("Path exists and writable")
			
			#read reports and create delta
			if os.path.getctime(args[0]) < os.path.getctime(args[1]):
				#file1 is bigger
				LOGGER.info("Assuming file1 ('"+args[0]+"') is the first snapshot.")
				f1 = file1.readlines()
				f2 = file2.readlines()
				f1.sort()
				f2.sort()
				diff = difflib.ndiff(f1, f2)
				this_date = datetime.datetime.fromtimestamp(os.path.getmtime(args[1])).strftime('%Y-%m-%d')
				#set vlog
				if options.verificationLog == "":
					if os.access(datetime.datetime.fromtimestamp(os.path.getmtime(args[0])).strftime('%Y%m%d')+"_satprep.vlog", os.W_OK):
						options.verificationLog = datetime.datetime.fromtimestamp(os.path.getmtime(args[0])).strftime('%Y%m%d')+"_satprep.vlog"
				elif os.access(options.verificationLog, os.W_OK) != True:
					if os.access(datetime.datetime.fromtimestamp(os.path.getmtime(args[0])).strftime('%Y%m%d')+"_satprep.vlog", os.W_OK):
						options.verificationLog = datetime.datetime.fromtimestamp(os.path.getmtime(args[0])).strftime('%Y%m%d')+"_satprep.vlog"
					else: options.verificationLog = ""
				if options.verificationLog != "": LOGGER.info(options.verificationLog + " seems to be our verification log")
				else: LOGGER.info("Snapshot and monitoring checkboxes won't be pre-selected as we don't have a valid .vlog!")
			else:
				#file2 is bigger
				LOGGER.info("Assuming file2 ('"+args[1]+"') is the first snapshot.")
				f1 = file1.readlines()
                                f2 = file2.readlines()
                                f1.sort()
                                f2.sort()
				diff = difflib.ndiff(f1, f2)
				this_date = datetime.datetime.fromtimestamp(os.path.getmtime(args[0])).strftime('%Y-%m-%d')
				#set vlog
				if options.verificationLog == "":
					if os.access(datetime.datetime.fromtimestamp(os.path.getmtime(args[1])).strftime('%Y%m%d')+"_satprep.vlog", os.W_OK):
						options.verificationLog = datetime.datetime.fromtimestamp(os.path.getmtime(args[1])).strftime('%Y%m%d')+"_satprep.vlog"
				elif os.access(options.verificationLog, os.W_OK) != True:
					if os.access(datetime.datetime.fromtimestamp(os.path.getmtime(args[1])).strftime('%Y%m%d')+"_satprep.vlog", os.W_OK):
						options.verificationLog = datetime.datetime.fromtimestamp(os.path.getmtime(args[1])).strftime('%Y%m%d')+"_satprep.vlog"
					else: options.verificationLog = ""
				if options.verificationLog != "": LOGGER.info(options.verificationLog + " seems to be our verification log")
				else:
					LOGGER.info("Snapshot and monitoring checkboxes won't be pre-selected as we don't have a valid .vlog!")
					vlogInvalid=True
			
			#read vlog
			if vlogInvalid == False:
				f_log = open(options.verificationLog, 'r')
				vlog = f_log.read()
				LOGGER.debug("vlog is:\n" + vlog)
			else: vlog=""
			
			#create delta
			delta = ''.join(x[2:] for x in diff if x.startswith('- '))
			delta = "".join([s for s in delta.strip().splitlines(True) if s.strip("\r\n").strip()])
			
			#print delta
			if options.debug: LOGGER.debug("Delta is:\n"+delta)
			
			#create diff CSV report
			f = open( options.output+'.csv', 'w' )
			f.write(header)
			for line in delta:
				f.write(line)
			f.close()
			
			#stop here if user doesn't want any fancy host reports
			if options.noHostReports:
				LOGGER.info("Creation of host reports skipped as you don't want any fancy reports.")
				exit(1)
			
			#create _all_ the PDF reports
			
			# STYLE DISCLAIMER
			# ----------------
			# I know that the following code is just a mess from the view of an advanced Python coder.
			# I'm quite new to Python and still learning. So if you have any relevant hints let me know.
			
                        #switch to /tmp directory
                        os.chdir("/tmp")
			
			#read CSV as array
			a = []
			if options.debug: LOGGER.debug("Opening file '" + options.output+'.csv' + "'")
			csvReader = csv.reader(open(thisFolder+"/"+options.output+'.csv', 'r'), delimiter=';');
			for row in csvReader:
				a.append(row);
			
			#create array with hosts
			hosts = []
			for i in range(0, len(a)):
				if str(a[i][0]) not in hosts and str(a[i][0]) != "hostname":
					hosts.append(a[i][0])
			
			#open TeX template
			with open (thisFolder+"/"+options.template+".tex", "r") as template:
				data=template.read()
				template.close()
			
			#create patch report per host
			for host in hosts:
				#scan imported data
				
				#flag for NoReboot Box and notes
				this_NoReboot="$\Box$"
				this_RebootNotes=""
				
				#LaTeX line including the the errata-relevant columns for this host
				thisColDescriptor=""
				
				#LaTeX lines for the table
				this_errataTable="\section*{}"
				this_errataTable=this_errataTable + "\n" + '\\begin{tabularx}{\\textwidth}{%%colDescriptor}'
				this_errataTable=this_errataTable + "\n" + '\hline'
				this_errataTable=this_errataTable + "\n" + '\multicolumn{%%count}{|c|}{\cellcolor{Gray}\\textbf{List of installed patches}} \\\\'
				this_errataTable=this_errataTable + "\n" + '\\hline'
				
				#set multicolumn counter (table header)
				this_errataColumns = [row for row in repcols if row.find("errata") != -1]
				this_errataTable = this_errataTable.replace("%%count", str(len(this_errataColumns)))
				
				#set LaTeX column descriptor (table header)
				for i in range(0, len(this_errataColumns)):
					if this_errataColumns[i] == "errata_desc" or this_errataColumns[i] == "errata_name":
						thisColDescriptor = thisColDescriptor + " | X"
					else:
						thisColDescriptor = thisColDescriptor + " | l"
				thisColDescriptor = thisColDescriptor + " | "
				this_errataTable = this_errataTable.replace("%%colDescriptor", thisColDescriptor)
				
				#add LaTeX columns (table header)
				tempRow="\n"
				count=1
				for row in this_errataColumns:
					#avoid & if last column
					tempRow=tempRow + '\\textbf{' + row + '} '
					if count != len(this_errataColumns): tempRow = tempRow + '& '
					count = count +1
				#end column row and replace variable names with human-readable names
				tempRow = tempRow + '\\\\'
				tempRow = tempRow.replace("errata_name", "Name").replace("errata_date", "Date").replace("errata_desc","Description").replace("errata_reboot", "Reboot required").replace("errata_type", "Type")
				this_errataTable = this_errataTable + tempRow
				
				#read the diff file content sequentially (Yeah I know that this is pretty bad)
				this_errata_name=[]
				this_errata_date=[]
				this_errata_desc=[]
				this_errata_reboot=[]
				this_errata_type=[]
				for line in a:
						#check if the current line is host-relevant
						if line[0] == host:
							if options.debug: LOGGER.debug("Found relevant line for " + host + ": " + str(line))
							#define IP address if present in report
							if repcols["ip"] < 666:
								this_ip = line[repcols["ip"]]
								this_host = host + "\n(" + line[repcols["ip"]] + ")"
							else:
								#just set host
								this_host = host
								this_ip = ""
							
							#set owner if present in report
							if repcols["system_owner"] < 666:
								this_owner = line[repcols["system_owner"]]
								this_owner = this_owner.replace('%%nl', '\newline')
							else:
								this_owner = ""
							
							#set system cluster bit if specified and present in report
				                        if repcols["system_cluster"] < 666 and line[repcols["system_cluster"]] == "1":
								#set cluster/standalone boxes
								this_cluster = "$\CheckedBox$"
								this_standalone = "$\Box$"
								hintsClTest=""
                                                        else:
								#set cluster/standalone boxes
                                                                this_cluster = "$\Box$"
								this_standalone = "$\CheckedBox$"
								hintsClTest="not a cluster system"
							
							#set system monitoring bit if specified and present in report
							if repcols["system_monitoring"] < 666 and line[repcols["system_monitoring"]] == "0":
								#no monitoring, add notes if available
                                                                this_monSchedNo = "$\CheckedBox$"
							else:
								#set box/comment if downtime scheduled
								if repcols["system_monitoring_name"] < 666 and line[repcols["system_monitoring_name"]] != "":
									tempHost = line[repcols["system_monitoring_name"]]
									if "@" in tempHost: tempHost = tempHost[:tempHost.find("@")]
								else: tempHost = host
								if "MONOK;"+host in vlog:
									LOGGER.debug("MONOK;"+tempHost + " in vlog!")
									this_monYes = "$\CheckedBox$"
									this_monNo = "$\Box$"
								else:
									LOGGER.debug("MONOK;"+tempHost + " NOT in vlog!")
									this_monYes = "$\Box$"
									if vlogInvalid == False: this_monNo = "$\CheckedBox$"
									else: this_monNo = "$\Box$"
							if repcols["system_monitoring_notes"] < 666 and len(line[repcols["system_monitoring_notes"]]) > 1:
                                                               	this_monNotes = line[repcols["system_monitoring_notes"]]
							else: this_monNotes = ""
							
                                                        #set system backup bit if specified and present in report
                                                        if repcols["system_backup"] < 666 and line[repcols["system_backup"]] == "0":
                                                                #no backup, add notes if available
                                                                this_backupNo = "$\CheckedBox$"
                                                                if repcols["system_backup_notes"] < 666 and len(line[repcols["system_backup_notes"]]) > 1:
                                                                        this_backupNoNotes = line[repcols["system_backup_notes"]]
                                                                else:
                                                                        this_backupNoNotes = ""
                                                        else:
                                                                this_backupNo = "$\Box$"
                                                                this_backupNoNotes = ""

                                                        #set system antivir bit if specified and present in report
                                                        if repcols["system_antivir"] < 666 and line[repcols["system_antivir"]] == "0":
                                                                #no antivirus, add notes if available
                                                                this_antivirNo = "$\CheckedBox$"
                                                                if repcols["system_antivir_notes"] < 666 and len(line[repcols["system_antivir_notes"]]) > 1:
                                                                        this_antivirNoNotes = line[repcols["system_antivir_notes"]]
                                                                else:
                                                                        this_antivirNoNotes = ""
                                                        else:
                                                                this_antivirNo = "$\Box$"
                                                                this_antivirNoNotes = ""

							#set system virtualization bit if specified and present in report
                                                        if repcols["system_virt"] < 666 and line[repcols["system_virt"]] == "1":
								#set boxes and notes
                                                                this_hwCheckNo = "$\CheckedBox$"
								this_hwCheckNotes = "not a physical host"
								this_vmSnapNotes = ""
								#set box/comment if snapshot created
								if repcols["system_virt_vmname"] < 666 and line[repcols["system_virt_vmname"]] != "":
									tempHost = line[repcols["system_virt_vmname"]]
									if "@" in tempHost: tempHost = tempHost[:tempHost.find("@")]
								else: tempHost = host
								if "SNAPOK;"+tempHost in vlog:
									LOGGER.debug("SNAPOK;"+tempHost + " in vlog!")
									this_vmSnapYes = "$\CheckedBox$"
									this_vmSnapNo = "$\Box$"
								else:
									LOGGER.debug("SNAPOK;"+tempHost + " NOT in vlog!")
									this_vmSnapYes = "$\Box$"
									if vlogInvalid == False: this_vmSnapNo = "$\CheckedBox$"
                                                        else:  
								#set boxes and notes
								this_hwCheckNo = "$\Box$"
								this_vmSnapNo = "$\CheckedBox$"
								this_hwCheckNotes = ""
								this_vmSnapNotes ="not a virtual machine"
							
							#set reboot box if specified and present in report
							if repcols["errata_reboot"] < 666 and line[repcols["errata_reboot"]] != "reboot_suggested":
								this_NoReboot="$\CheckedBox$"
								this_RebootNotes="no reboot required"
							
							#set errata information
							if repcols["errata_name"] < 666 and line[repcols['errata_name']] != "":
								this_errata_name.append(line[repcols["errata_name"]])
							if repcols["errata_date"] < 666 and line[repcols['errata_date']] != "":
								this_errata_date.append(line[repcols["errata_date"]])
							if repcols["errata_desc"] < 666 and line[repcols["errata_desc"]] != "":
								this_errata_desc.append(line[repcols["errata_desc"]])
							if repcols["errata_type"] < 666 and line[repcols["errata_type"]] != "":
								this_errata_type.append(line[repcols["errata_type"]])
							if repcols["errata_reboot"] < 666 and line[repcols["errata_reboot"]] != "":
								this_errata_reboot.append(line[repcols["errata_reboot"]])
				
                                #add errata
				tempRow=""
				for i in range(0, len(this_errata_name)):
                                	count=1
	                                for row in this_errataColumns:
        	                                #avoid & if last column
                	                        tempRow=tempRow +  row + " "
                        	                if count != len(this_errataColumns): tempRow = tempRow + ' & '
                                	        count = count +1
	                                #end column row and replace variable names with human-readable names
        	                        tempRow = tempRow + "\\\\" + "\n"
                	                tempRow = tempRow.replace("errata_name", this_errata_name[i])
					if repcols["errata_date"] < 666:
						 tempRow = tempRow.replace("errata_date", this_errata_date[i])
					else:
						tempRow = tempRow.replace("errata_date", "unknown ")
					if repcols["errata_desc"] < 666:
						tempRow = tempRow.replace("errata_desc", this_errata_desc[i])
					else:
						tempRow = tempRow.replace("errata_desc", "unknown ")
					if repcols["errata_reboot"] < 666:
						if this_errata_reboot[i] == "1":
							tempRow = tempRow.replace("errata_reboot", "yes")
						else:
							tempRow = tempRow.replace("errata_reboot", "no")
					else:
						tempRow = tempRow.replace("errata_reboot", "unknown ")
					if repcols["errata_type"] < 666:
						tempRow = tempRow.replace("errata_type", this_errata_type[i])
					else:
						tempRow = tempRow.replace("errata_type", "unknown ")
				
				tempRow = tempRow.replace("_", "\_")
                                this_errataTable = this_errataTable + "\n" + tempRow

                                #print table footer
                                this_errataTable = this_errataTable + "\n" + '\hline' + "\n" + '\end{tabularx}'
				
				#Write LaTeX file
				with open (host.replace(" ","") + ".tex", "w") as letter:
					s = LaTeXTemplate(data)
					#Substitute template variables
					letter.write(s.substitute(titleHostname=host, ip=this_ip, date=this_date, owner=this_owner, systemStandalone=this_standalone, systemCluster=this_cluster, hintsClusterTest=hintsClTest, hwCheckNo=this_hwCheckNo, hwCheckNotes=this_hwCheckNotes, vmSnapYes=this_vmSnapYes, vmSnapNo=this_vmSnapNo, vmSnapNotes=this_vmSnapNotes, rebootNo=this_NoReboot, rebootNotes=this_RebootNotes, errata=this_errataTable, orientation=options.pageOrientation+",", footer=options.footer, logo=options.logoImage, monSchedYes=this_monYes, monSchedNo=this_monNo, monSchedNotes=this_monNotes, BackupNo=this_backupNo, BackupNoNotes=this_backupNoNotes, AntivirNo=this_antivirNo, AntivirNoNotes=this_antivirNoNotes))
					letter.close();
					#render PDF files
					os.system(options.pathPdflatex + " %s %s 1>/dev/null" % ("--interaction=batchmode",  host.replace(" ","") + ".tex"))
					#remove .tex/.aux/.log file
					if options.preserveTex == False:
						if options.debug: LOGGER.debug("Removing "+host+".[tex|aux|log|out] files")
						os.remove(host.replace(" ","") + ".tex")
						os.remove(host.replace(" ","") + ".aux")
						os.remove(host.replace(" ","") + ".log")
						os.remove(host.replace(" ","") + ".out")
		else:   
			#path not writable or existent
			LOGGER.error("Path non-existent or non-writable!")
	else:
		#template not existent
		LOGGER.error("LaTeX template file ("+thisFolder+"/"+options.template+".[tpl|tex]) non-existent!")



if __name__ == "__main__":
	(options, args) = parse_options()
	
	if options.debug:
		logging.basicConfig(level=logging.DEBUG)
		LOGGER.setLevel(logging.DEBUG)
	else:
		logging.basicConfig()
		LOGGER.setLevel(logging.INFO)
	
	main(options)
