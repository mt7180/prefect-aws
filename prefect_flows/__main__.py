
import sys
from prefect_flows import send_newsletters

# Access command-line arguments, if '-deploy' argument is given, 
# prefect flow will be deployed, else locally executed
if len(sys.argv) > 1 and sys.argv[1] == '-deploy':
    deploy = True
else:
    deploy = False

send_newsletters.main(deploy=deploy)