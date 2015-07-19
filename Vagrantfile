# -*- coding: utf-8 -*-
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.define "master", primary: true do |master|
      master.vm.box = "ubuntu/trusty64"
      master.vm.box_check_update = true

      master.ssh.forward_x11 = true
      master.ssh.forward_agent = true

      # A to jest zamiast serwera devpi - tam budujemy pakiety Pythona i każdy host może tam coś od siebie wrzucić:
      master.vm.synced_folder "../wheelhouse", "/wheelhouse", mount_options: ["dmode=777", "fmode=666"], owner: "vagrant"
      # ... i takie dopalenie dla pip(1)
      master.vm.synced_folder "../pip-cache/http", "/pip-cache-http", mount_options: ["dmode=775", "fmode=664"], owner: "vagrant"
      master.vm.synced_folder "../pip-cache/wheels", "/pip-cache-wheels", mount_options: ["dmode=775", "fmode=664"], owner: "vagrant"

      master.vm.network "private_network", ip: "192.168.111.100"
	  
      master.vm.network "forwarded_port", guest: 5432, host: 15432
	  master.vm.network "forwarded_port", guest: 80, host: 8080

      master.vm.provider "virtualbox" do |vb|
         vb.gui = true
         vb.memory = "2048"
      end

      if Vagrant.has_plugin?("vagrant-proxyconf")
        master.proxy.http     = "http://192.168.111.1:8123/"
        master.proxy.https    = "http://192.168.111.1:8123/"
        master.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,.localnet,messaging-test"
      end
	  
      master.vm.provision "shell", path: "provisioning/master.sh"

      master.vm.provision "file", source: "provisioning/lxterminal.desktop", destination: "/home/vagrant/Desktop/lxterminal.desktop"

      master.vm.provision "file", source: "../GNUPG-keys/gpg.conf", destination: "/home/vagrant/.gpg/gpg.conf"
      master.vm.provision "file", source: "../GNUPG-keys/pubring.gpg", destination: "/home/vagrant/.gpg/pubring.gpg"
      master.vm.provision "file", source: "../GNUPG-keys/random_seed", destination: "/home/vagrant/.gpg/random_seed"
      master.vm.provision "file", source: "../GNUPG-keys/secring.gpg", destination: "/home/vagrant/.gpg/secring.gpg"
      master.vm.provision "file", source: "../GNUPG-keys/trustdb.gpg", destination: "/home/vagrant/.gpg/trustdb.gpg"

      master.vm.provision "shell", path: "provisioning/master-post-file.sh"

      if Vagrant.has_plugin?("vagrant-reload")
        master.vm.provision :reload
      end
  end

  config.vm.define "staging" do |staging|
      staging.vm.box = "ubuntu/trusty64"
      staging.vm.box_check_update = false

      staging.vm.network "private_network", ip: "192.168.111.101"

      if Vagrant.has_plugin?("vagrant-proxyconf")
        staging.proxy.http     = "http://192.168.111.1:8123/"
        staging.proxy.https    = "http://192.168.111.1:8123/"
        staging.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,master,messaging-test.localnet,.localnet,messaging-test"
	  end

      staging.vm.provision "shell", path: "provisioning/staging.sh"
  end
end