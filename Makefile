#NAME: Amir Saad, Kuan Xiang Wen
#EMAIL: arsaad@g.ucla.edu, kuanxw@g.ucla.edu
#ID: 604840359, 004461554

default:
	cp lab3b.py lab3b
	chmod u+x lab3b lab3b.py

clean:
	rm -f *.tar.gz lab3b

dist: clean default
	tar -zcvf lab3b-604840359.tar.gz lab3b.py Makefile README

check: dist
	./P3B_check.sh 604840359