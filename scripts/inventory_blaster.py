#!/usr/bin/env python3
"""Read-only static inventory of one immutable upstream Git tree; no Lean execution."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess

COMMIT = 'b7cc5304bde87c269bb3ba57e560304ffd9f2189'
REPO = 'https://github.com/input-output-hk/Blaster-benchmarking'
CATALOG_ID = 'blaster-full-inventory-b7cc5304-v1'
CATALOG_PATH = 'benchmarks/blaster-full-inventory.json'
LOCK_PATH = 'benchmarks/blaster-full-inventory.lock.json'
BUILDER_PATH = 'scripts/inventory_blaster.py'
PILOT_PATH = 'benchmarks/blaster-nng4-v1.json'
PILOT_LOCK_PATH = 'benchmarks/blaster-nng4-v1.lock.json'
LICENSE_PATH = 'benchmarks/upstream/blaster-b7cc5304/LICENSE'
FIRST_RUN_PATH = 'benchmarks/results/blaster-nng4-first-run.json'
PROTECTED_PATHS = [BUILDER_PATH, PILOT_PATH, PILOT_LOCK_PATH, LICENSE_PATH, FIRST_RUN_PATH]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mask_lean(source):
    """Mask nested comments and strings, retaining offsets and newlines."""
    result = list(source)
    index, depth, string = 0, 0, False
    while index < len(source):
        if depth:
            if source.startswith('/-', index):
                result[index:index+2] = '  '; depth += 1; index += 2
            elif source.startswith('-/', index):
                result[index:index+2] = '  '; depth -= 1; index += 2
            else:
                if source[index] != '\n': result[index] = ' '
                index += 1
        elif string:
            if source[index] == '\\':
                result[index] = ' '; index += 1
                if index < len(source):
                    if source[index] != '\n': result[index] = ' '
                    index += 1
            else:
                if source[index] == '"': string = False
                if source[index] != '\n': result[index] = ' '
                index += 1
        elif source.startswith('--', index):
            end = source.find('\n', index)
            if end < 0: end = len(source)
            result[index:end] = ' ' * (end-index); index = end
        elif source.startswith('/-', index):
            result[index:index+2] = '  '; depth = 1; index += 2
        elif source[index] == '"':
            result[index] = ' '; string = True; index += 1
        else:
            index += 1
    if depth or string:
        raise ValueError('Unterminated comment/string')
    return ''.join(result)


DECLARATION = re.compile(r'(?m)^[ \t]*(?:(?:private|protected|noncomputable|unsafe)\s+)*(theorem|lemma|example)\b')


def declarations(source):
    clean = mask_lean(source)
    matches = list(DECLARATION.finditer(clean))
    rows = []
    for ordinal, match in enumerate(matches, 1):
        limit = matches[ordinal].start() if ordinal < len(matches) else len(clean)
        nesting = []
        marker = None
        for index in range(match.end(), limit):
            char = clean[index]
            if char in '([{': nesting.append(char)
            elif char in ')]}':
                if not nesting: raise ValueError('Unbalanced header')
                nesting.pop()
            elif clean.startswith(':=', index) and not nesting:
                marker = index
                break
        if marker is None: raise ValueError('Header proof separator missing')
        name = None
        if match[1] != 'example':
            name_match = re.match(r'\s+([^\s:({]+)', source[match.end():])
            if not name_match: raise ValueError('Declaration name missing')
            name = name_match[1]
        header = source[match.start():marker+2]
        rows.append({'source_kind': match[1], 'source_name': name,
                     'source_declaration_ordinal': ordinal,
                     'source_line': source.count('\n', 0, match.start())+1,
                     'header': header, 'header_sha256': sha(header.encode()),
                     'header_end_line': source.count('\n', 0, marker+2)+1,
                     'header_parse': 'lexically_delimited_not_elaborated'})
    return rows


def nng_contexts(source, rows):
    by_line = {row['source_line']: row for row in rows}
    lines = source.splitlines()
    scopes = []
    index = 0
    while index < len(lines):
        raw = lines[index]; line = raw.strip(); index += 1
        if index in by_line:
            row = by_line[index]
            context = [command for scope in scopes for command in scope['commands']]
            row['context'] = context
            row['context_closers'] = ['end '+scope['name'] for scope in reversed(scopes)]
            row['full_name'] = ('.'.join([scope['name'] for scope in scopes if scope['kind']=='namespace'] + [row['source_name']])
                                if row['source_name'] else None)
            statement = json.dumps({'context':context, 'header':row['header']},ensure_ascii=False,separators=(',',':'))
            row['statement_sha256'] = sha(statement.encode())
            row['context_reconstruction'] = 'proof_free_active_source_commands_not_elaborated'
            proof = lines[row['header_end_line']-1].split(':=',1)[1].strip()
            if proof not in {'by sorry','by decide +native'}:
                raise ValueError('Unsupported NNG4 proof layout: '+proof)
            index = row['header_end_line']
            continue
        if not line or line.startswith('--'): continue
        block = re.fullmatch(r'(namespace|section) ([\w.]+)',line)
        if block:
            scopes.append({'kind':block[1],'name':block[2],'commands':[raw]}); continue
        ending = re.fullmatch(r'end(?: ([\w.]+))?',line)
        if ending:
            if not scopes or (ending[1] and ending[1]!=scopes[-1]['name']): raise ValueError('NNG scope mismatch')
            scopes.pop(); continue
        if line in {'abbrev ℕ := Nat','open Nat'}:
            scopes[-1]['commands'].append(raw); continue
        raise ValueError('Unsupported NNG4 context: '+line)
    require(not scopes,'Unclosed NNG4 source scope')


def build_inventory(source_root, project_root):
    """Reconstruct all metadata from the pinned checkout without running its code."""
    ROOT, PROJECT = Path(source_root), Path(project_root)
    require(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==COMMIT,
            'Upstream checkout is not at the immutable inventory commit')
    tree = subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','-z','HEAD'])
    files = []
    for entry in tree.split(b'\0'):
        if not entry: continue
        meta,path = entry.split(b'\t',1)
        mode,kind,blob = meta.decode().split()
        require(kind=='blob' and mode in {'100644','100755'},'Unsupported upstream Git tree entry')
        path = path.decode()
        data = safe_file(ROOT,path).read_bytes()
        require(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob,
                'Source bytes differ from pinned Git blob: '+path)
        files.append({'path':path,'git_blob':blob,'sha256':sha(data),'bytes':len(data), 'kind':'lean' if path.endswith('.lean') else 'support'})
    indexed = {row['path']:row for row in files}
    config_path = 'benchmarks/benchmark_config.sh'
    config = (ROOT/config_path).read_text()
    specs = re.findall(r'^    "([^:"]+):([^:"]+):([^:"]+):(\d+)(?::([^"\n]+))?"$',config,re.M)
    require(len(specs)==12,'Pinned official suite index does not contain twelve recognized entries')
    all_rows, families = [], []
    for imp,path,family,timeout,mode in specs:
        mode = mode or 'stmt'
        paths = [item['path'] for item in files if item['path'].startswith(path+'/') and item['path'].endswith('.lean') and '/' not in item['path'][len(path)+1:]] if mode=='taskdir' else [path]
        family_rows = []
        warnings = []
        for file_path in sorted(paths):
            source = (ROOT/file_path).read_text()
            rows = declarations(source)
            if family=='NNG4': nng_contexts(source,rows)
            first = next((row for row in rows if row['source_kind']=='theorem'),None)
            if mode=='taskdir' and len(rows)!=1:
                warnings.append({'path':file_path,'kind':'multiple_proof_declarations_first_theorem_is_runner_target',
                                 'target':first['source_name'] if first else None,
                                 'other_declarations':[row['source_name'] for row in rows if row is not first]})
            clean = mask_lean(source)
            imports = re.findall(r'(?m)^\s*import\s+([^\n]+)',clean)
            imports = [item.strip() for line in imports for item in line.split()]
            support_counts = dict(collections.Counter(re.findall(r'(?m)^[ \t]*(?:(?:private|protected|noncomputable|unsafe)\s+)*(def|abbrev|inductive|structure|instance|macro_rules|macro|syntax|elab|axiom|opaque)\b',clean)))
            indexed[file_path].update(family=family,imports=imports,support_declaration_counts=support_counts,
                                      proof_declaration_count=len(rows),source_links=sorted(set(re.findall(r'https://[^\s<>]+',source))))
            first_line = rows[0]['source_line'] if rows else len(source.splitlines())+1
            indexed[file_path]['support_prefix_sha256'] = sha(''.join(source.splitlines(keepends=True)[:first_line-1]).encode())
            for row in rows:
                canonical = row['source_kind']=='theorem' and (mode=='stmt' or row is first)
                canonical_id = 'blaster-b7cc5304/'+family+'/'+file_path+'#decl-'+str(row['source_declaration_ordinal'])
                prefix = ''.join(source.splitlines(keepends=True)[:row['source_line']-1])
                row.update(canonical_case_id=canonical_id, family=family, canonical_runner_member=canonical,
                           runner_goal_id=Path(file_path).stem if mode=='taskdir' else row['source_name'],
                           runner_mode=mode, source_repository=REPO, source_commit=COMMIT,
                           source_path=file_path, source_git_blob=indexed[file_path]['git_blob'], source_sha256=indexed[file_path]['sha256'],
                           source_url=REPO+'/blob/'+COMMIT+'/'+file_path+'#L'+str(row['source_line']),
                           imports=imports,measurement_status='not_measured', proof_body_policy='replace_entire_upstream_proof_with_exactly_by_colony',
                           source_prefix_sha256=sha(prefix.encode()),
                           context_reconstruction=row.get('context_reconstruction','not_reconstructed_no_runnable_case_claim'))
                # This identity binds header bytes and support provenance, not
                # a claim that the support closure is safe/runnable on Colony.
                identity = {'header':row['header'], 'source_path':file_path,
                            'source_commit':COMMIT,'source_file_sha256':row['source_sha256'],
                            'source_prefix_sha256':row['source_prefix_sha256']}
                row['statement_identity_sha256'] = sha(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode())
                if 'context' in row:
                    row['proof_free_context_sha256'] = sha(json.dumps(row['context'],ensure_ascii=False,separators=(',',':')).encode())
                row['target_integrity'] = 'canonical_target'
                row['integration_status'] = 'not_admitted'
                if mode=='taskdir' and len(rows)!=1:
                    row['runner_target_ambiguity']=True
                    if canonical:
                        row['target_integrity']='upstream_harness_targets_helper'
                        row['integration_status']='blocked'
                        intended = rows[-1]
                        row['intended_final_specification'] = {key:intended[key] for key in
                            ('source_name','source_line','header','header_sha256')}
                if not canonical: row['exclusion_reason']='unnamed_examples_not_enumerated_by_upstream_runner' if row['source_kind']=='example' else 'later_declaration_truncated_by_upstream_taskdir_proof_swap'
                if family in {'STG4','MiniF2F','Verina'}: row['integration_blockers']=['Pinned compatible Mathlib dependency and proof-free support extraction require governance review','Statement elaboration on Colony toolchain untested']
                elif family=='NNG4': row['integration_blockers']=['Only first12 admitted to existing strict pilot; remaining declarations not measured','No claim that all mathematical goals are currently tractable']
                elif family.startswith('UPLC'): row['integration_blockers']=['Preserve original evaluator definitions, program and fuel; governed extraction/admission not performed','No correspondence claim to full Cardano or Plutus execution']
                elif family.endswith('Home'): row['integration_blockers']=['Upstream home-turf goals already adapt external sources; preserve pinned adapted statements','Imports and elaboration compatibility require case-specific governed admission']
                else: row['integration_blockers']=['Governed proof-free context extraction and elaboration admission not performed']
                if row['target_integrity']=='upstream_harness_targets_helper':
                    row['integration_blockers'].insert(0,'Upstream harness targets a helper and truncates the final program specification; separate governed target clarification required')
                all_rows.append(row); family_rows.append(row)
        families.append({'id':family,'official_spec':':'.join((imp,path,family,timeout))+(':'+mode if mode=='taskdir' else ''),
                         'mode':mode,'source_path':path,'file_count':len(paths),'canonical_case_count':sum(row['canonical_runner_member'] for row in family_rows),
                         'declarations':dict(collections.Counter(row['source_kind'] for row in family_rows)),
                         'upstream_timeout_seconds':int(timeout),'warnings':warnings})
    manifest_bytes = (PROJECT/PILOT_PATH).read_bytes()
    pilot_lock_bytes = (PROJECT/PILOT_LOCK_PATH).read_bytes()
    manifest = json.loads(manifest_bytes)
    require(manifest['source']['commit']==COMMIT,'Pilot source commit differs from full catalog')
    old_report_path=FIRST_RUN_PATH
    old_report=json.loads((PROJECT/old_report_path).read_text())
    pilot_rows={row['id']:row for row in old_report['cases']}
    matches=0
    for case in manifest['cases']:
        candidates=[row for row in all_rows if row['source_path']==manifest['source']['path'] and row['source_line']==case['source_line']]
        require(len(candidates)==1,'Pilot source location is not uniquely cataloged')
        row=candidates[0]
        for field in ('header','context','statement_sha256','full_name'):
            require(row[field]==case[field],'Pilot statement/context differs: '+field)
        require(row['source_sha256']==manifest['source']['sha256'],'Pilot source file hash differs')
        require(row['source_git_blob']==manifest['source']['git_blob'],'Pilot source Git blob differs')
        evidence=pilot_rows[case['id']]
        require(evidence['header']==case['header'] and evidence['statement_sha256']==case['statement_sha256'],
                'Historical pilot evidence statement differs')
        row['measurement_status']='historical_strict_pilot_measurement_available'
        row['integration_status']='existing_strict_pilot'
        row['pilot_mapping']={'corpus_id':manifest['id'],'case_id':case['id'],'statement_sha256':case['statement_sha256'],
                              'manifest_path':PILOT_PATH,'manifest_sha256':sha(manifest_bytes),
                              'lock_path':PILOT_LOCK_PATH,'lock_sha256':sha(pilot_lock_bytes),
                              'historical_report_path':old_report_path,'historical_report_sha256':sha((PROJECT/old_report_path).read_bytes()),
                              'historical_source_revision':old_report['source_revision'],
                              'historical_colony_status':evidence['results']['colony']['status'],
                              'mapping_rule':'exact repository/commit/path/blob/filehash/source_line/header/context/statementhash match; never case-id alone'}
        matches+=1
    require(matches==12,'Expected twelve exact pilot bindings')
    counts=collections.Counter(row['source_kind'] for row in all_rows)
    canonical=sum(row['canonical_runner_member'] for row in all_rows)
    require(canonical==671 and counts=={'theorem':674,'example':9},'Pinned canonical/declaration counts changed')
    # Independently inspect every Lean file, including supporting framework files.
    extra=[]
    for item in files:
        if item['kind']=='lean' and 'family' not in item:
            item['classification']='support_not_in_official_suite_index'
            extra.extend(declarations((ROOT/item['path']).read_text()))
    require(not extra,'An unconfigured supporting Lean file contains unclassified proof declarations')
    header_counts = collections.Counter(row['header_sha256'] for row in all_rows if row['canonical_runner_member'])
    inventory={'schema':'colony.blaster_north_star_inventory.v1','id':CATALOG_ID,
               'source':{'repository':REPO,'commit':COMMIT,'url':REPO+'/tree/'+COMMIT,
                'license':'Apache-2.0','license_sha256':indexed['LICENSE']['sha256'],'toolchain':(ROOT/'lean-toolchain').read_text().strip(),
                'suite_index':config_path,'suite_index_sha256':indexed[config_path]['sha256'],
                'canonical_runner':'latest/run_latest.sh -> benchmarks/benchmark_config.sh -> benchmarks/benchmark_core.sh',
                'read_only_checkout':True,'upstream_code_executed':False},
               'scope':'Complete static inventory of tracked source at pinned commit, with canonical slots following explicit latest-runner configuration; no full-suite evaluation or certified runnable corpus claim.',
               'summary':{'families':len(families),'tracked_files':len(files),'lean_files':sum(x['kind']=='lean' for x in files),
                          'suite_lean_files':sum(x['file_count'] for x in families),'canonical_runner_slots':canonical,
                          'named_theorems':counts['theorem'],'named_lemmas':counts['lemma'],'unnamed_examples':counts['example'],
                          'support_or_noncanonical_proof_declarations':len(all_rows)-canonical,
                          'historical_pilot_measured':matches,'canonical_not_measured':canonical-matches,'not_measured_is_not_failure':True,
                          'exact_header_duplicate_groups':sum(count>1 for count in header_counts.values()),
                          'exact_header_duplicate_members':sum(count for count in header_counts.values() if count>1),
                          'exact_header_duplicate_excess':sum(count-1 for count in header_counts.values()),
                          'full_suite_score':None,'runnable_full_suite':False},
               'parser':{'kind':'Python static lexical inventory; nested comments/strings masked; balanced delimiters locate exact declaration headers',
                         'lean_parser_or_elaborator_used':False,'header_count_crosscheck':'674 named theorem commands +9 anonymous examples; no named lemmas; all671 runner targets have located proof separators',
                         'proof_free_context_reconstructed':'All108 named NNG4 declarations and9 anonymous NNG4 examples; only12 have existing governed measurement',
                         'limitations':['Not a Lean grammar implementation; arbitrary macros, command quotations or generated declarations could evade static enumeration',
                                        'Per-source imports recorded; full transitive import/definition closure is not certified',
                                        'Source-prefix hashes bind original provenance and may cover earlier proof text; only explicit proof_free_context fields describe reconstructed proof-free support',
                                        'File/theorem counts do not establish statement validity, non-vacuity, solvability or score',
                                        'Existing strict evaluator intentionally admits only its frozen12 cases; inventory cannot expand that policy',
                                        'NNG4 anonymous examples have Type-valued targets and are not upstream canonical theorem slots',
                                        'Original upstream proof bodies, including sorry/native bodies, are provenance only and must never supply target proofs']},
               'denominator_notes':['671 canonical slots come from12 entries in benchmark_config.sh used by latest/run_latest.sh, not every theorem/helper in every Lean file',
                                    'Slots are not a claim of671 distinct mathematical theorems; preserve all five Home families even when statements duplicate or adapt the same external source',
                                    'Exact-header duplicate counts are byte-level diagnostics only, include declaration names, and do not establish semantic equivalence or deduplicate the denominator',
                                    'benchmark.conf contains an older two-suite example override; report which entry point/config is used',
                                    'Two Verina task files contain multiple theorem declarations; upstream swap_proof selects the first helper theorem and truncates later specs, flagged per family/case',
                                    'UPLC generator lists6 depth sizes but7 checked-in depth files exist; frozen source index includes d_sum_16',
                                    'Upstream root toolchain is4.24; latest runner fetches moving tool branches/toolchains. Colony rehost4.35 cannot claim an official same-toolchain Blaster comparison'],
               'dependencies':json.loads((ROOT/'lake-manifest.json').read_text())['packages'],
               'families':families,'files':files,'declarations':all_rows}
    return inventory


def safe_file(root, relative):
    root = Path(root)
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe inventory resource path')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink inventory resource')
    if not current.is_file(): raise ValueError('Missing inventory resource: '+relative)
    return current


def freeze(source_root, project_root):
    project_root = Path(project_root)
    catalog = build_inventory(source_root, project_root)
    encoded = (json.dumps(catalog,ensure_ascii=False,indent=2)+'\n').encode()
    (project_root/CATALOG_PATH).write_bytes(encoded)
    lock = {'schema':'colony.blaster_north_star_inventory_lock.v1','catalog_id':CATALOG_ID,
            'catalog':{'path':CATALOG_PATH,'sha256':sha(encoded)},
            'source':{'repository':REPO,'commit':COMMIT,
                      'files_sha256':sha(json.dumps(catalog['files'],ensure_ascii=False,separators=(',',':')).encode())},
            'protected_files':{path:sha(safe_file(project_root,path).read_bytes()) for path in PROTECTED_PATHS}}
    (project_root/LOCK_PATH).write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
    return catalog


def load_inventory(project_root):
    """Validate published metadata/lock locally; never fetch or run upstream."""
    encoded = safe_file(project_root,CATALOG_PATH).read_bytes()
    catalog = json.loads(encoded)
    lock = json.loads(safe_file(project_root,LOCK_PATH).read_bytes())
    if (catalog.get('schema')!='colony.blaster_north_star_inventory.v1' or catalog.get('id')!=CATALOG_ID
            or catalog.get('source',{}).get('repository')!=REPO or catalog['source'].get('commit')!=COMMIT
            or lock.get('schema')!='colony.blaster_north_star_inventory_lock.v1' or lock.get('catalog_id')!=CATALOG_ID
            or lock.get('catalog')!={'path':CATALOG_PATH,'sha256':sha(encoded)}
            or lock.get('protected_files')!={path:sha(safe_file(project_root,path).read_bytes()) for path in PROTECTED_PATHS}
            or lock.get('source')!={'repository':REPO,'commit':COMMIT,
                'files_sha256':sha(json.dumps(catalog.get('files'),ensure_ascii=False,separators=(',',':')).encode())}):
        raise ValueError('Inventory differs from its frozen source/metadata lock')
    canonical=[row for row in catalog.get('declarations',[]) if row.get('canonical_runner_member')]
    if (len(canonical)!=671 or len(catalog.get('families',[]))!=12
            or len({row['canonical_case_id'] for row in canonical})!=671
            or sum(row.get('target_integrity')=='upstream_harness_targets_helper' for row in canonical)!=2):
        raise ValueError('Canonical inventory denominator or target ambiguities changed')
    return catalog


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Read-only checkout of the exact pinned upstream commit')
    parser.add_argument('--write',action='store_true',help='Write reviewed metadata and lock from --source')
    arguments=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    if arguments.write:
        if arguments.source is None: parser.error('--write requires --source')
        catalog=freeze(arguments.source,root)
    else:
        catalog=load_inventory(root)
        if arguments.source is not None and catalog!=build_inventory(arguments.source,root):
            raise ValueError('Pinned source reconstruction differs from frozen inventory')
    print(json.dumps(catalog['summary'],indent=2))


if __name__=='__main__':
    main()
