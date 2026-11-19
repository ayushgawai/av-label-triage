#!/usr/bin/env python3
"""Generate native Auto Ontology YAML for the read-only AV triage snapshot."""
import uuid
import yaml


def uid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://avtriage.local/ontology/'+name))


def definitions():
    tables = {
      'reopened_summary':['release_id','policy_id','reopened_images','evidence_ids'],
      'current_reviews':['id','release_id','incident_id','image_id','policy_id','decision','actor_type','supersedes_id'],
      'audit_results':['design_id','release_id','incident_id','policy_id','population','sampled','completed','status','estimate','lower_bound','upper_bound'],
      'policy_exclusions':['evidence_id','release_id','policy_id','incident_id','image_id'],
    }
    table_defs=[]; terms=[]
    for table,columns in tables.items():
        table_id=uid(table)
        table_defs.append({'id':table_id,'name':table,'description':'Read-only vetted AV Label Triage snapshot','pk':[],'type':'VIEW','columns':[{'id':uid(table+'.'+c),'name':c,'description':'','type':'','sample_values':[],'is_nullable':True,'is_unique':False} for c in columns]})
        terms.append({'id':uid('term.'+table),'name':table,'description':{'reopened_summary':'Certified distinct reopened image counts grouped by release and policy with review event evidence IDs','current_reviews':'Current unsuperseded review events and their evidence IDs','audit_results':'Certified finite-population estimates and bounds from the statistical library','policy_exclusions':'Reviewed exclusions with evidence IDs'}[table], 'represents':[table_id], 'columns_attributes':[{'id':uid('attribute.'+table+'.'+c),'name':c,'description':'','column_id':uid(table+'.'+c)} for c in columns]})
    return {'data_layer':{'databases':[{'id':uid('database'),'dialect':'postgresql','schemas':[{'id':uid('schema'),'name':'avtriage','database_name':'triage','tables':table_defs}]}],'foreign_keys':[],'joins':[{'source_table_id':uid('current_reviews'),'target_table_id':uid('policy_exclusions'),'join_columns':[{'source':'id','target':'evidence_id'}]}]},'semantic_layer':{'terms':terms,'semantic_fks':[],'sql_attributes':{'manual':[],'table':[],'sql':[],'bridge_table':[]},'custom_analyses':[]},'zones':[]}


if __name__=='__main__': print(yaml.safe_dump(definitions(),sort_keys=False))
