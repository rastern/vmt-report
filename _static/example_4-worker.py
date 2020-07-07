# Dump selected fields from all market actions
import arbiter
import vmtreport
import umsg

# source worker sub-process must accept 3 parameters
def actions(source, config, logger):
    umsg.log(f"Retrieving data from {config['resource']}", logger=logger)

    # source.connect() gives us the vmt-connect.Connection instance returned by
    # vmt-report; here we use the get_actions() method inline.
    # Another use would be the standard vmt-connect idiom:
    #   vmt = source.connection()
    #   res = vmt.get_action()
    res = source.connect().get_actions()

    fields = ['createTime', 'actionType', 'details']
    return [{x: res[x]} for x in res if x in fields]

if __name__ == '__main__':
  report = arbiter.Process('report.config', actions)
  report.run()
