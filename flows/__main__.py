
import sys
#from flows import send_report
from . import send_report

# Access command-line arguments, if '-deploy' argument is given, 
# prefect flow will be deployed, else locally executed
if len(sys.argv) > 1 and sys.argv[1] == '-deploy':
    deploy = True
else:
    deploy = False

# execute or deploy (depends on deploy parameter) the prefect flow to send an email with an 
# updated dashboard report to each registered user
send_report.main(deploy=deploy)