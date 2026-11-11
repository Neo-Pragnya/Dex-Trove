/* Monthly claims summary: a representative program for the SAS server tests */
libname raw '/data/raw';
%let minamt = 100;

data work.claims;
  set raw.claims;
  where status ne 'VOID';
  if amount = . then amount_flag = 'M';
  else if amount < &minamt then amount_flag = 'S';
  else amount_flag = 'L';
  net = amount - discount;
  ratio = discount / amount;
  if region = 'TEST' then delete;
  length amount_flag $1;
  keep id region amount discount net ratio amount_flag;
run;

proc sort data=work.claims out=work.sorted nodupkey;
  by region descending amount;
run;

proc means data=work.claims nway noprint;
  class region;
  var amount net;
  output out=work.summary n(amount)=n_claims sum(amount)=total mean(net)=avg_net;
run;

proc freq data=work.claims;
  tables amount_flag / out=work.flags;
run;

%macro report(ds);
  proc print data=&ds; run;
%mend;
%report(work.summary);

* running total needs RETAIN, which isn't translated;
data work.running;
  set work.sorted;
  retain cum 0;
  cum = cum + amount;
run;

proc reg data=work.claims;
  model net = amount;
run;
