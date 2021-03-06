#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os

from git      import *
from gitdb    import IStream
from StringIO import StringIO

class PageNotFound ( Exception ):
    def __init__ ( self, name ):
        self.name = name
    def __str__ ( self ):
        return 'Page (%s) is not found' % ( self.name )

class Wiki ( object ):
    def __init__ ( self, repository, extension, homepage ):
        self.homepage   = homepage
        self.extension  = extension

        if os.path.isdir( os.path.join( repository, '.git' ) ):
            self.repository = Repo( repository, odbt=GitDB )
        else:
            if not os.path.isdir( repository ):
                os.makedirs( repository )

            os.chdir( repository )
            self.repository = Repo.init()

    def find_all ( self ):
        repo  = self.repository

        if len(repo.refs) == 0:
            return []
        else:
            pages = []
            for entry in repo.tree().traverse():
                if entry.type == 'blob':
                    pages.append( Page( entry, repo ) )
            
            return pages

    def find ( self, name ):
        blob = self.find_blob(name)

        if blob is None:
            raise PageNotFound( name )

        return Page(blob, self.repository)

    def find_blob ( self, path ):
        repo = self.repository

        if len(repo.refs) == 0:
            return None
        else:
            tree = repo.tree()
            blob = None

            try:
                blob = tree/("%s.%s" % ( path, self.extension ))
            except KeyError, e:
                pass

            return blob

    def find_or_create ( self, name, content='' ):
        try:
            return self.find( name )
        except PageNotFound, e:
            page = Page( self.create_blob_for(name, data=content), self.repository )
            page.commit('Page (%s) is created.' % ( name ))
            return page

    def create_blob_for ( self, path, data='' ):
        repo    = self.repository
        istream = IStream('blob', len(data), StringIO(data))
        
        repo.odb.store( istream )
        blob    = Blob( repo, istream.binsha, 0100644, "%s.%s" % ( path, self.extension ) )

        return blob

class Page ( object ):
    def __init__ ( self, blob, repository ):
        self.blob       = blob
        self.repository = repository

    def __str__ ( self ):
        return self.blob.name

    def name ( self ):
        return os.path.splitext( self.blob.name )[0]

    def content ( self ):
        try:
            return self.blob.data_stream.read()
        except AttributeError, e:
            return None

    def update_content ( self, new ):
        if self.content == new:
            return None

        fh = open( self.blob.abspath, 'w' )
        fh.write( new )
        fh.close()

        return self.commit('Updated: %s' % ( self.blob.name ))

    def commit ( self, message ):
        index = self.repository.index
        blob  = self.blob

        if os.path.isfile( blob.abspath ):
            index.add([ blob.path ])
        else:
            index.add([ IndexEntry.from_blob( blob ) ])

        return index.commit( message );

from flask import Flask, render_template, redirect, url_for, request
from config import REPOSITORY, FILE_EXTENSION, HOMEPAGE

wiki = Wiki( REPOSITORY, FILE_EXTENSION, HOMEPAGE )
app  = Flask(__name__)

@app.route('/favicon.ico')
def favicon ():
    return redirect( url_for('static', filename='favicon.ico') )

@app.route('/')
def toppage ():
    try:
        data = wiki.find( wiki.homepage )
        return render_template('page.html', page=data)
    except PageNotFound, notfound:
        return redirect( url_for('edit_page', page=wiki.homepage) )

@app.route('/pages')
def index_page():
    pages = wiki.find_all()
    return render_template('pages.html', pages=pages)

@app.route('/<page>/edit')
def edit_page ( page ):
    data = wiki.find_or_create( page )
    return render_template('edit.html', page=data)

@app.route('/<page>', methods=[ 'GET' ])
def view_page ( page ):
    try:
        data = wiki.find( page )
        return render_template('page.html', page=data)
    except PageNotFound, notfound:
        return redirect( url_for('edit_page', page=page) )

@app.route('/<page>', methods=[ 'POST' ])
def update_page ( page ):
    data = wiki.find_or_create( page )
    body = request.form.get('body', '')
    data.update_content( body )

    return redirect( url_for('view_page', page=page) )

application = app
