# -*- coding: utf-8 -*-
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.define "master", primary: true do |master|
      master.vm.box = "mpasternak/trusty64-updated"
      master.vm.box_check_update = false

      master.ssh.forward_x11 = true
      master.ssh.forward_agent = true

      master.vm.synced_folder "/Users/mpasternak/Dropbox/GIT", "/GIT", mount_options: ["dmode=775", "fmode=664"], owner: "vagrant"

      master.vm.network "private_network", ip: "192.168.111.100"
	  
      master.vm.network "forwarded_port", guest: 5432, host: 15432
	  master.vm.network "forwarded_port", guest: 80, host: 8080

      master.vm.provider "virtualbox" do |vb|
         vb.gui = false
	 vb.cpus = "2"
         vb.memory = "1024"
      end

      if Vagrant.has_plugin?("vagrant-proxyconf")
        master.proxy.http     = "http://192.168.111.1:3128/"
        master.proxy.https    = "http://192.168.111.1:3128/"
        master.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,.localnet,messaging-test"
      end
	  
      master.vm.provision "shell", path: "provisioning/master.sh"

      # Potrzebne do budowania pakietu nginxa... tym moze sie zajac np jakas inna masyzna wirtualna - w przyszlosci... 
      # master.vm.provision "file", source: "/Volumes/Dane zaszyfrowane/Klucze GPG - Ubuntu/gpg.conf", destination: "/home/vagrant/.gnupg/gpg.conf"
      # master.vm.provision "file", source: "/Volumes/Dane zaszyfrowane/Klucze GPG - Ubuntu/pubring.gpg", destination: "/home/vagrant/.gnupg/pubring.gpg"
      # master.vm.provision "file", source: "/Volumes/Dane zaszyfrowane/Klucze GPG - Ubuntu/random_seed", destination: "/home/vagrant/.gnupg/random_seed"
      # master.vm.provision "file", source: "/Volumes/Dane zaszyfrowane/Klucze GPG - Ubuntu/secring.gpg", destination: "/home/vagrant/.gnupg/secring.gpg"
      # master.vm.provision "file", source: "/Volumes/Dane zaszyfrowane/Klucze GPG - Ubuntu/trustdb.gpg", destination: "/home/vagrant/.gnupg/trustdb.gpg"

      master.vm.provision "shell", path: "provisioning/master-post-file.sh"

  end

  config.vm.define "staging" do |staging|
      staging.vm.box = "mpasternak/trusty64-updated"
      staging.vm.box_check_update = false

      staging.vm.network "private_network", ip: "192.168.111.101"

      if Vagrant.has_plugin?("vagrant-proxyconf")
        staging.proxy.http     = "http://192.168.111.1:3128/"
        staging.proxy.https    = "http://192.168.111.1:3128/"
        staging.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,master,messaging-test.localnet,.localnet,messaging-test"
	  end

      staging.vm.provision "shell", path: "provisioning/staging.sh"
  end

  config.vm.define "selenium", primary: true do |selenium|
      selenium.vm.box = "mpasternak/trusty64-updated"
      selenium.vm.box_check_update = false

      selenium.ssh.forward_x11 = true
      selenium.ssh.forward_agent = true

      selenium.vm.network "private_network", ip: "192.168.111.150"

      if Vagrant.has_plugin?("vagrant-proxyconf")
        selenium.proxy.http     = "http://192.168.111.1:3128/"
        selenium.proxy.https    = "http://192.168.111.1:3128/"
        selenium.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,.localnet,messaging-test"
      end
	  
      selenium.vm.provider "virtualbox" do |vb|
         vb.gui = false
         vb.memory = "1024"
	 vb.cpus = "2"
      end

      selenium.vm.provision "shell", path: "provisioning/selenium.sh"

      selenium.vm.provision "file", source: "provisioning/selenium.conf", destination: "050-selenium.conf"
      selenium.vm.provision "shell", inline: "mv 050-selenium.conf /etc/supervisor/conf.d/050-selenium.conf"
      selenium.vm.provision "shell", inline: "service supervisor restart"

  end
end
