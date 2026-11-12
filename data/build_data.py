"""Builds the verified .gov data package used by the pipeline.
Raw values below were retrieved on 2026-11-12 from the .gov URLs listed in provenance.json.
Integrity checks run on every build; the script aborts if any check fails."""
import csv, json, sys

# (name, USPS code, Census region, Census division, July 1 2025 resident population estimate)
S = [
("Alabama","AL","South","East South Central",5193088),("Alaska","AK","West","Pacific",737270),
("Arizona","AZ","West","Mountain",7623818),("Arkansas","AR","South","West South Central",3114791),
("California","CA","West","Pacific",39355309),("Colorado","CO","West","Mountain",6012561),
("Connecticut","CT","Northeast","New England",3688496),("Delaware","DE","South","South Atlantic",1059952),
("District of Columbia","DC","South","South Atlantic",693645),("Florida","FL","South","South Atlantic",23462518),
("Georgia","GA","South","South Atlantic",11302748),("Hawaii","HI","West","Pacific",1432820),
("Idaho","ID","West","Mountain",2029733),("Illinois","IL","Midwest","East North Central",12719141),
("Indiana","IN","Midwest","East North Central",6973333),("Iowa","IA","Midwest","West North Central",3238387),
("Kansas","KS","Midwest","West North Central",2977220),("Kentucky","KY","South","East South Central",4606864),
("Louisiana","LA","South","West South Central",4618189),("Maine","ME","Northeast","New England",1414874),
("Maryland","MD","South","South Atlantic",6265347),("Massachusetts","MA","Northeast","New England",7154084),
("Michigan","MI","Midwest","East North Central",10127884),("Minnesota","MN","Midwest","West North Central",5830405),
("Mississippi","MS","South","East South Central",2954160),("Missouri","MO","Midwest","West North Central",6270541),
("Montana","MT","West","Mountain",1144694),("Nebraska","NE","Midwest","West North Central",2018006),
("Nevada","NV","West","Mountain",3282188),("New Hampshire","NH","Northeast","New England",1415342),
("New Jersey","NJ","Northeast","Middle Atlantic",9548215),("New Mexico","NM","West","Mountain",2125498),
("New York","NY","Northeast","Middle Atlantic",20002427),("North Carolina","NC","South","South Atlantic",11197968),
("North Dakota","ND","Midwest","West North Central",799358),("Ohio","OH","Midwest","East North Central",11900510),
("Oklahoma","OK","South","West South Central",4123288),("Oregon","OR","West","Pacific",4273586),
("Pennsylvania","PA","Northeast","Middle Atlantic",13059432),("Rhode Island","RI","Northeast","New England",1114521),
("South Carolina","SC","South","South Atlantic",5570274),("South Dakota","SD","Midwest","West North Central",935094),
("Tennessee","TN","South","East South Central",7315076),("Texas","TX","South","West South Central",31709821),
("Utah","UT","West","Mountain",3538904),("Vermont","VT","Northeast","New England",644663),
("Virginia","VA","South","South Atlantic",8880107),("Washington","WA","West","Pacific",8001020),
("West Virginia","WV","South","South Atlantic",1766147),("Wisconsin","WI","Midwest","East North Central",5972787),
("Wyoming","WY","West","Mountain",588753),
]
US_TOTAL = 341784857
REGIONS = {"Northeast":58042054,"Midwest":69762666,"South":133833983,"West":80146154}
DIVISIONS = {"New England":15431980,"Middle Atlantic":42610074,"East North Central":47693655,
 "West North Central":22069011,"South Atlantic":70198706,"East South Central":20069188,
 "West South Central":43566089,"Mountain":26346149,"Pacific":53800005}

errs = []
if len(S) != 51: errs.append(f"expected 51 rows, got {len(S)}")
tot = sum(r[4] for r in S)
if tot != US_TOTAL: errs.append(f"sum {tot} != US total {US_TOTAL} (diff {tot-US_TOTAL})")
for k,v in REGIONS.items():
    s = sum(r[4] for r in S if r[2]==k)
    if s != v: errs.append(f"region {k}: {s} != {v}")
for k,v in DIVISIONS.items():
    s = sum(r[4] for r in S if r[3]==k)
    if s != v: errs.append(f"division {k}: {s} != {v}")
if len({r[1] for r in S}) != 51: errs.append("duplicate codes")
if errs:
    print("INTEGRITY FAIL"); [print(" -",e) for e in errs]; sys.exit(1)
print(f"OK  51 rows | sum={tot:,} == US total | 4 regions + 9 divisions match")

rows = sorted(S, key=lambda r: -r[4])
with open("data/state_pop_2025.csv","w",newline="") as f:
    w = csv.writer(f); w.writerow(["code","name","region","division","population","rank_of_51"])
    for i,r in enumerate(rows,1): w.writerow([r[1],r[0],r[2],r[3],r[4],i])

# NASA planetary fact sheet, 'Diameter (km)', page last updated 18 March 2025
PL = [("Pluto",2376),("Moon",3475),("Mercury",4879),("Mars",6792),("Venus",12104),("Earth",12756),
      ("Neptune",49528),("Uranus",51118),("Saturn",120536),("Jupiter",142984)]
with open("data/planet_diameters.csv","w",newline="") as f:
    w = csv.writer(f); w.writerow(["body","diameter_km"]); w.writerows(PL)

# dollar benchmarks used by the 'neon_doubling' style
BM = [
 {"value":87460.0,"label":"MEDIAN HOUSEHOLD INCOME","detail":"Census Bureau, Income in the United States: 2025 (real, 2025 dollars)"},
 {"value":40559796589243.37,"label":"TOTAL PUBLIC DEBT OUTSTANDING","detail":"Treasury Fiscal Data, Debt to the Penny, 2026-11-09"},
]
json.dump(BM, open("data/dollar_benchmarks.json","w"), indent=1)
print("wrote state_pop_2025.csv, planet_diameters.csv, dollar_benchmarks.json")
