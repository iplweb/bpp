update import_dbf_poz
set tresc = '884$ #a$ 28940458 #b$' || E'\r\n' ||
            '#985$ #a$|0000005891#b$#c$' || E'\r\n' ||
            '#969$ #a$|00000'
where idt = 81868
  and lp = 3;

with h as (with fuj as (select imiona || ' ' || nazwisko as x, idt_aut as y from import_dbf_aut where exp_id = idt_aut)
           select x, array_agg(y) as y
           from fuj
           group by x
           having count(*) > 1)
update import_dbf_aut
set exp_id = h.y[0]
from h
where idt_aut = h.y[1];
with fuj as (select imiona || ' ' || nazwisko as x, idt_aut as y from import_dbf_aut where exp_id = idt_aut)
select x, array_agg(y)
from fuj
group by x
having count(*) > 1;

with h as (with fuj as (
    select replace(imiona, ' ', '-') || '-' || nazwisko as x, idt_aut as y from import_dbf_aut where exp_id = idt_aut
)
           select x, array_agg(y) as y
           from fuj
           group by x
           having count(*) > 1)
update import_dbf_aut
set exp_id = h.y[0]
from h
where idt_aut = h.y[1];

with fuj as (
    select replace(imiona, ' ', '-') || '-' || nazwisko as x, idt_aut as y from import_dbf_aut where exp_id = idt_aut
)
select x, array_agg(y)
from fuj
group by x
having count(*) > 1;

