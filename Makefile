zebr0:
	mkdir target
	find . -name __pycache__ | xargs rm -rf
	cd src && zip -r ../target/zebr0.zip *
	echo "#!/usr/bin/python3 -u" | cat - target/zebr0.zip > target/zebr0
	chmod +x target/zebr0

clean:
	rm -rf target
