# -*- coding: utf-8 -*-
# -*- mode: ruby -*-
# vi: set ft=ruby :

# DPI pod Windows

Vagrant.configure(2) do |config|

  config.vm.define "master", primary: true do |master|
      master.vm.box = "ubuntu/trusty64"
      master.vm.box_check_update = false

      master.ssh.forward_x11 = true
      master.ssh.forward_agent = true

      # Ansible playbooks zarządzające serwisami - prosta sprawa:
      master.vm.synced_folder "../ANSIBLE-django-bpp/playbooks", "/home/vagrant/ansible-playbooks-bpp", mount_options: ["dmode=700", "fmode=600"], owner: "vagrant"

      # To jest potrzebne do budowania pakietów nginx, aby potem je móc podpisać i wrzucić do PPA na launchpad
      master.vm.synced_folder "../ANSIBLE-django-bpp/.gnupg", "/home/vagrant/.gnupg", mount_options: ["dmode=700", "fmode=600"], owner: "vagrant"
	  
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
	  
      master.vm.provision "shell", inline: <<-SHELL

        # Extra swap
        dd if=/dev/zero of=/swapfile bs=1M count=2048
        mkswap /swapfile
        swapon /swapfile
        sudo -s bash -c "echo swapon /swapfile > /etc/rc.local"
        sudo -s bash -c "echo exit 0 >> /etc/rc.local"


        # Basic APT stuff
        sudo apt-get update -qq
        sudo apt-get dist-upgrade -y
        sudo apt-get install -y git mercurial build-essential mc emacs24-nox yaml-mode python-dev python3-dev sshpass links redis-server jed lxde xinit

        # firefox=28.0+build2-0ubuntu2

        # PIP, Virtualenv
        wget https://bootstrap.pypa.io/get-pip.py

        sudo python get-pip.py
        sudo python3 get-pip.py

        sudo pip2 install virtualenv
        sudo pip3 install virtualenv

        # Git global config
        git config --global user.email "michal.dtz@gmail.com"
        git config --global user.name "Michał Pasternak"
        git config --global core.autocrlf true

        # Ansible
        sudo pip2 install ansible redis

        # Hosts
		echo "# Moje hosty: " >> /etc/hosts
		echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
		echo "10.0.2.2 gate" >> /etc/hosts		
		echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
        echo "192.168.111.101 staging" >> /etc/hosts

        # Hostname
        echo "master" > /etc/hostname
        hostname `cat /etc/hostname`

        # User config
        su vagrant -c "git config --global user.email michal.dtz@gmail.com"
        su vagrant -c "git config --global user.name Michał\ Pasternak"
        su vagrant -c "git config --global core.autocrlf true"
        su vagrant -c "echo alias\ jed=emacs24-nox >> ~/.bashrc"
		su vagrant -c "mkdir -p ~/.cache/pip && cd ~/.cache/pip && ln -s /pip-cache-http http && ln -s /pip-cache-wheels wheels"

      SHELL
  end

  config.vm.define "staging" do |staging|
      staging.vm.box = "ubuntu/trusty64"
      staging.vm.box_check_update = false

      # A to jest zamiast serwera devpi - tam budujemy pakiety Pythona i każdy host może tam coś od siebie wrzucić:
      staging.vm.synced_folder "../wheelhouse", "/wheelhouse", mount_options: ["dmode=777", "fmode=666"]
      # ... i takie dopalenie dla pip(1)
      staging.vm.synced_folder "../pip-cache", "/home/vagrant/.cache/pip", mount_options: ["dmode=775", "fmode=664"]

      staging.vm.network "private_network", ip: "192.168.111.101"

      if Vagrant.has_plugin?("vagrant-proxyconf")
        staging.proxy.http     = "http://192.168.111.1:8123/"
        staging.proxy.https    = "http://192.168.111.1:8123/"
        staging.proxy.no_proxy = "localhost,127.0.0.1,.example.com,staging,master,messaging-test.localnet,.localnet,messaging-test"
	  end

      staging.vm.provision "shell", inline: <<-SHELL
        sudo apt-get update -qq
        sudo apt-get dist-upgrade -y
        sudo apt-get install -y sshpass jed emacs24-nox

        # Hosts
		echo "# Moje hosty: " >> /etc/hosts
		echo "192.168.111.1 thinkpad thinkpad.localnet" >> /etc/hosts
		echo "10.0.2.2 gate" >> /etc/hosts		
		echo "192.168.111.100 master master.localnet  messaging-test.localnet messaging-test" >> /etc/hosts
        echo "192.168.111.101 staging" >> /etc/hosts
		
        echo "staging" > /etc/hostname
        hostname `cat /etc/hostname`

      SHELL
  end

end
